using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal static class WebViewPortableLauncher
{
    private const string ProductName = "FreshdeskLocalExporter";
    private const string AppResourceName = "FreshdeskLocalExporter.Payload.app.zip";
    private const string PythonResourceName = "FreshdeskLocalExporter.Payload.python-runtime.zip";
    private const int BackendRequestTimeoutMilliseconds = 30 * 60 * 1000;

    private static HttpListener uiServer;
    private static Process backendProcess;
    private static volatile int backendPort;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetDllDirectory(string lpPathName);

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            AppDomain.CurrentDomain.AssemblyResolve += ResolveEmbeddedAssembly;
            if (args.Length == 2 && args[0] == "--extract-python")
            {
                ExtractPythonRuntime(args[1]);
                return 0;
            }

            string launcherPath = Process.GetCurrentProcess().MainModule.FileName;
            string launcherDir = Path.GetDirectoryName(launcherPath) ?? Directory.GetCurrentDirectory();
            string appDir = PrepareAppCache(launcherPath);
            string resourcesDir = Path.Combine(appDir, "resources");
            WriteTextWithRetry(Path.Combine(resourcesDir, "portable-root.txt"), launcherDir);

            StartPythonRuntimeExtraction(appDir);

            backendPort = ReadPortOverride("FRESH_EXPORTER_BACKEND_PORT", GetFreePort());
            int uiPort = GetFreePort();
            StartUiServer(Path.Combine(resourcesDir, "app", "dist"), uiPort);
            ThreadPool.QueueUserWorkItem(_ => StartBackendWhenReady(appDir, backendPort, uiPort, launcherDir));

            RunWebViewWindow(uiPort, appDir);
            Cleanup();
            return 0;
        }
        catch (Exception error)
        {
            try
            {
                File.WriteAllText(
                    Path.Combine(Path.GetTempPath(), "FreshdeskLocalExporter-launch-error.txt"),
                    error.ToString()
                );
            }
            catch { }
            Cleanup();
            return 1;
        }
    }

    private static string PrepareAppCache(string launcherPath)
    {
        // Cache the embedded app by launcher build so startup only extracts a
        // fresh payload after the portable executable changes.
        FileInfo launcher = new FileInfo(launcherPath);
        string cacheRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            ProductName
        );
        Directory.CreateDirectory(cacheRoot);

        string cacheKey = Math.Abs((launcher.Length.ToString() + launcher.LastWriteTimeUtc.Ticks).GetHashCode()).ToString("x");
        string appDir = Path.Combine(cacheRoot, "webview-" + cacheKey);
        string marker = Path.Combine(appDir, ".complete");
        string distIndex = Path.Combine(appDir, "resources", "app", "dist", "index.html");
        if (File.Exists(marker) && File.Exists(distIndex))
        {
            return appDir;
        }

        string staging = Path.Combine(cacheRoot, "staging-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        try
        {
            ExtractResourceZip(AppResourceName, staging);
            File.WriteAllText(Path.Combine(staging, ".complete"), DateTime.UtcNow.ToString("O"));
            if (Directory.Exists(appDir))
            {
                Directory.Delete(appDir, true);
            }
            MoveDirectoryWithRetry(staging, appDir);
            return appDir;
        }
        catch
        {
            if (Directory.Exists(staging))
            {
                try { Directory.Delete(staging, true); } catch { }
            }
            throw;
        }
    }

    private static void StartUiServer(string distDir, int uiPort)
    {
        // The WebView uses one loopback origin for static assets and API calls
        // so the backend session cookie behaves the same as it does in desktop use.
        uiServer = new HttpListener();
        uiServer.Prefixes.Add("http://127.0.0.1:" + uiPort + "/");
        uiServer.Start();
        ThreadPool.QueueUserWorkItem(_ =>
        {
            while (uiServer != null && uiServer.IsListening)
            {
                try
                {
                    HttpListenerContext context = uiServer.GetContext();
                    ThreadPool.QueueUserWorkItem(__ => HandleRequest(context, distDir));
                }
                catch
                {
                    break;
                }
            }
        });
    }

    private static void HandleRequest(HttpListenerContext context, string distDir)
    {
        try
        {
            string path = context.Request.Url.AbsolutePath;
            if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
            {
                ProxyApi(context);
                return;
            }
            ServeStatic(context, distDir);
        }
        catch
        {
            try
            {
                context.Response.StatusCode = 500;
                byte[] body = Encoding.UTF8.GetBytes("Internal server error");
                context.Response.OutputStream.Write(body, 0, body.Length);
                context.Response.Close();
            }
            catch { }
        }
    }

    private static void ServeStatic(HttpListenerContext context, string distDir)
    {
        string rawPath = Uri.UnescapeDataString(context.Request.Url.AbsolutePath.TrimStart('/'));
        if (String.IsNullOrWhiteSpace(rawPath))
        {
            rawPath = "index.html";
        }

        string root = Path.GetFullPath(distDir);
        string candidate = Path.GetFullPath(Path.Combine(root, rawPath.Replace('/', Path.DirectorySeparatorChar)));
        if (!candidate.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        {
            context.Response.StatusCode = 403;
            context.Response.Close();
            return;
        }

        string filePath = File.Exists(candidate) ? candidate : Path.Combine(root, "index.html");
        context.Response.ContentType = ContentTypeFor(filePath);
        using (FileStream input = File.OpenRead(filePath))
        {
            context.Response.ContentLength64 = input.Length;
            input.CopyTo(context.Response.OutputStream);
        }
        context.Response.Close();
    }

    private static void ProxyApi(HttpListenerContext context)
    {
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + backendPort + context.Request.RawUrl);
            request.Method = context.Request.HttpMethod;
            request.AllowAutoRedirect = false;
            request.ContentType = context.Request.ContentType;
            request.Timeout = BackendRequestTimeoutMilliseconds;
            request.ReadWriteTimeout = BackendRequestTimeoutMilliseconds;

            foreach (string headerName in context.Request.Headers.AllKeys)
            {
                if (String.Equals(headerName, "Host", StringComparison.OrdinalIgnoreCase) ||
                    String.Equals(headerName, "Content-Length", StringComparison.OrdinalIgnoreCase) ||
                    String.Equals(headerName, "Connection", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                try { request.Headers[headerName] = context.Request.Headers[headerName]; } catch { }
            }

            if (context.Request.HasEntityBody)
            {
                using (Stream output = request.GetRequestStream())
                {
                    context.Request.InputStream.CopyTo(output);
                }
            }

            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
                CopyProxyResponse(response, context.Response);
            }
        }
        catch (WebException error)
        {
            HttpWebResponse response = error.Response as HttpWebResponse;
            if (response != null)
            {
                CopyProxyResponse(response, context.Response);
                return;
            }
            context.Response.StatusCode = 502;
            context.Response.ContentType = "application/json";
            string detail = error.Status == WebExceptionStatus.Timeout
                ? "The local Freshdesk API took too long to respond."
                : "The local Freshdesk API is not available.";
            byte[] body = Encoding.UTF8.GetBytes("{\"detail\":\"" + detail + "\"}");
            context.Response.OutputStream.Write(body, 0, body.Length);
            context.Response.Close();
        }
    }

    private static void CopyProxyResponse(HttpWebResponse source, HttpListenerResponse target)
    {
        target.StatusCode = (int)source.StatusCode;
        target.ContentType = source.ContentType;
        foreach (string headerName in source.Headers.AllKeys)
        {
            if (String.Equals(headerName, "Content-Length", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(headerName, "Transfer-Encoding", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(headerName, "Connection", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(headerName, "Keep-Alive", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            try { target.Headers[headerName] = source.Headers[headerName]; } catch { }
        }
        using (Stream input = source.GetResponseStream())
        {
            if (input != null)
            {
                input.CopyTo(target.OutputStream);
            }
        }
        target.Close();
    }

    private static void StartBackendWhenReady(string appDir, int port, int uiPort, string launcherDir)
    {
        string resourcesDir = Path.Combine(appDir, "resources");
        string pythonExe = Path.Combine(resourcesDir, "python", "python.exe");
        string backendDir = Path.Combine(resourcesDir, "backend");
        Stopwatch timer = Stopwatch.StartNew();
        while (!File.Exists(pythonExe))
        {
            if (timer.Elapsed.TotalSeconds > 120)
            {
                throw new InvalidOperationException("The bundled Python runtime was not ready in time.");
            }
            Thread.Sleep(250);
        }

        string exportDir = Path.Combine(launcherDir, "exports");
        Directory.CreateDirectory(exportDir);
        ProcessStartInfo info = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = "backend_launcher.py",
            WorkingDirectory = backendDir,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        info.EnvironmentVariables["HOST"] = "127.0.0.1";
        info.EnvironmentVariables["PORT"] = port.ToString();
        info.EnvironmentVariables["EXPORT_DIR"] = exportDir;
        info.EnvironmentVariables["FRONTEND_ORIGINS"] = "http://127.0.0.1:" + uiPort;
        backendProcess = Process.Start(info);
    }

    private static void RunWebViewWindow(int uiPort, string appDir)
    {
        ExtractWebViewLoader(appDir);
        string userDataDir = Path.Combine(appDir, "webview-profile");
        Directory.CreateDirectory(userDataDir);
        SeedEdgeProfile(userDataDir);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new AppWindow("http://127.0.0.1:" + uiPort, userDataDir));
    }

    private static void SeedEdgeProfile(string userDataDir)
    {
        // WebView2 still creates an Edge profile. Seed only the preferences
        // needed to avoid first-run and sign-in prompts in the app shell.
        try
        {
            File.WriteAllText(Path.Combine(userDataDir, "First Run"), "");
            string defaultDir = Path.Combine(userDataDir, "Default");
            Directory.CreateDirectory(defaultDir);
            string preferences = "{" +
                "\"browser\":{\"has_seen_welcome_page\":true}," +
                "\"sync\":{\"promo_seen\":true,\"suppress_start\":true}," +
                "\"signin\":{\"allowed\":false}," +
                "\"credentials_enable_service\":false," +
                "\"profile\":{\"password_manager_enabled\":false}" +
                "}";
            File.WriteAllText(Path.Combine(defaultDir, "Preferences"), preferences);
            string localState = "{" +
                "\"browser\":{\"enabled_labs_experiments\":[]}," +
                "\"sync\":{\"disabled\":true}," +
                "\"signin\":{\"allowed\":false}," +
                "\"edge\":{\"first_run_complete\":true}" +
                "}";
            File.WriteAllText(Path.Combine(userDataDir, "Local State"), localState);
        }
        catch { }
    }

    private static Assembly ResolveEmbeddedAssembly(object sender, ResolveEventArgs args)
    {
        string name = new AssemblyName(args.Name).Name;
        string resourceName = null;
        if (name == "Microsoft.Web.WebView2.Core")
        {
            resourceName = "FreshdeskLocalExporter.WebView2.Core.dll";
        }
        else if (name == "Microsoft.Web.WebView2.WinForms")
        {
            resourceName = "FreshdeskLocalExporter.WebView2.WinForms.dll";
        }

        if (resourceName == null)
        {
            return null;
        }

        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
        {
            if (stream == null)
            {
                return null;
            }
            byte[] bytes = new byte[stream.Length];
            stream.Read(bytes, 0, bytes.Length);
            return Assembly.Load(bytes);
        }
    }

    private static void ExtractWebViewLoader(string appDir)
    {
        string loaderPath = Path.Combine(appDir, "WebView2Loader.dll");
        if (!File.Exists(loaderPath))
        {
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("FreshdeskLocalExporter.WebView2.Loader.dll"))
            {
                if (input == null)
                {
                    throw new InvalidOperationException("Embedded WebView2 loader was not found.");
                }
                using (FileStream output = File.Create(loaderPath))
                {
                    input.CopyTo(output);
                }
            }
        }
        SetDllDirectory(appDir);
    }

    private static void StartPythonRuntimeExtraction(string appDir)
    {
        // Runtime extraction can dominate cold startup. Let the UI open while a
        // helper process prepares Python before the backend launch waits on it.
        string pythonDir = Path.Combine(appDir, "resources", "python");
        string marker = Path.Combine(pythonDir, ".complete");
        string pythonExe = Path.Combine(pythonDir, "python.exe");
        if (File.Exists(marker) && File.Exists(pythonExe))
        {
            return;
        }

        string launcherPath = Process.GetCurrentProcess().MainModule.FileName;
        Process.Start(new ProcessStartInfo
        {
            FileName = launcherPath,
            Arguments = "--extract-python \"" + appDir + "\"",
            WorkingDirectory = Path.GetDirectoryName(launcherPath) ?? Directory.GetCurrentDirectory(),
            UseShellExecute = false,
            CreateNoWindow = true
        });
    }

    private static void ExtractPythonRuntime(string appDir)
    {
        string resourcesDir = Path.Combine(appDir, "resources");
        string pythonDir = Path.Combine(resourcesDir, "python");
        string marker = Path.Combine(pythonDir, ".complete");
        string pythonExe = Path.Combine(pythonDir, "python.exe");
        if (File.Exists(marker) && File.Exists(pythonExe))
        {
            return;
        }

        string staging = Path.Combine(resourcesDir, "python-staging-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        try
        {
            ExtractResourceZip(PythonResourceName, staging);
            File.WriteAllText(Path.Combine(staging, ".complete"), DateTime.UtcNow.ToString("O"));
            if (Directory.Exists(pythonDir))
            {
                Directory.Delete(pythonDir, true);
            }
            MoveDirectoryWithRetry(staging, pythonDir);
        }
        catch
        {
            if (Directory.Exists(staging))
            {
                try { Directory.Delete(staging, true); } catch { }
            }
            throw;
        }
    }

    private static void ExtractResourceZip(string resourceName, string destination)
    {
        using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
        {
            if (input == null)
            {
                throw new InvalidOperationException("Embedded payload was not found: " + resourceName);
            }
            using (ZipArchive archive = new ZipArchive(input, ZipArchiveMode.Read))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string filePath = Path.GetFullPath(Path.Combine(destination, entry.FullName));
                    string root = Path.GetFullPath(destination);
                    if (!filePath.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("The payload contained an unsafe path.");
                    }

                    if (String.IsNullOrEmpty(entry.Name))
                    {
                        Directory.CreateDirectory(filePath);
                        continue;
                    }

                    string parent = Path.GetDirectoryName(filePath);
                    if (!String.IsNullOrEmpty(parent))
                    {
                        Directory.CreateDirectory(parent);
                    }
                    entry.ExtractToFile(filePath, true);
                }
            }
        }
    }

    private static int GetFreePort()
    {
        TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }

    private static int ReadPortOverride(string name, int fallback)
    {
        string raw = Environment.GetEnvironmentVariable(name);
        int port;
        if (Int32.TryParse(raw, out port) && port > 0 && port < 65536)
        {
            return port;
        }
        return fallback;
    }

    private static void WriteTextWithRetry(string path, string content)
    {
        Exception lastError = null;
        byte[] bytes = Encoding.UTF8.GetBytes(content);
        for (int attempt = 0; attempt < 20; attempt++)
        {
            try
            {
                using (FileStream output = new FileStream(
                    path,
                    FileMode.Create,
                    FileAccess.Write,
                    FileShare.ReadWrite | FileShare.Delete
                ))
                {
                    output.Write(bytes, 0, bytes.Length);
                }
                return;
            }
            catch (Exception error)
            {
                lastError = error;
                Thread.Sleep(250);
            }
        }
        throw lastError;
    }

    private static string ContentTypeFor(string filePath)
    {
        switch (Path.GetExtension(filePath).ToLowerInvariant())
        {
            case ".html": return "text/html; charset=utf-8";
            case ".js": return "text/javascript; charset=utf-8";
            case ".css": return "text/css; charset=utf-8";
            case ".json": return "application/json; charset=utf-8";
            case ".svg": return "image/svg+xml";
            case ".ico": return "image/x-icon";
            case ".png": return "image/png";
            case ".jpg":
            case ".jpeg": return "image/jpeg";
            case ".webp": return "image/webp";
            case ".woff": return "font/woff";
            case ".woff2": return "font/woff2";
            default: return "application/octet-stream";
        }
    }

    private static void MoveDirectoryWithRetry(string source, string destination)
    {
        Exception lastError = null;
        for (int attempt = 0; attempt < 20; attempt++)
        {
            try
            {
                Directory.Move(source, destination);
                return;
            }
            catch (Exception error)
            {
                lastError = error;
                Thread.Sleep(250);
            }
        }
        throw lastError;
    }

    private static void Cleanup()
    {
        try
        {
            if (uiServer != null)
            {
                uiServer.Stop();
                uiServer.Close();
                uiServer = null;
            }
        }
        catch { }

        try
        {
            if (backendProcess != null && !backendProcess.HasExited)
            {
                backendProcess.Kill();
            }
        }
        catch { }
    }
}

internal sealed class AppWindow : Form
{
    private readonly string url;
    private readonly string userDataDir;
    private readonly WebView2 webView;

    public AppWindow(string url, string userDataDir)
    {
        this.url = url;
        this.userDataDir = userDataDir;
        Text = "Freshdesk Local Exporter";
        Width = 1240;
        Height = 860;
        MinimumSize = new System.Drawing.Size(980, 700);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.None;
        BackColor = System.Drawing.Color.FromArgb(244, 246, 251);

        webView = new WebView2();
        webView.Dock = DockStyle.Fill;
        Controls.Add(webView);
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        ApplyRoundedCorners();
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        ApplyRoundedCorners();
    }

    protected override async void OnShown(EventArgs e)
    {
        base.OnShown(e);
        await InitializeWebView();
    }

    private async Task InitializeWebView()
    {
        CoreWebView2EnvironmentOptions options = new CoreWebView2EnvironmentOptions(
            "--disable-sync --no-first-run --no-default-browser-check"
        );
        CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(
            null,
            userDataDir,
            options
        );
        await webView.EnsureCoreWebView2Async(environment);
        webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
        webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
        webView.CoreWebView2.WebMessageReceived += delegate(object sender, CoreWebView2WebMessageReceivedEventArgs args)
        {
            if (args.TryGetWebMessageAsString() == "drag-window")
            {
                BeginDrag();
            }
        };
        webView.CoreWebView2.AddHostObjectToScript("desktopWindow", new WindowBridge(this));
        await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(@"
            window.desktopWindow = {
              minimize: () => chrome.webview.hostObjects.desktopWindow.Minimize(),
              toggleMaximize: () => chrome.webview.hostObjects.desktopWindow.ToggleMaximize(),
              close: () => chrome.webview.hostObjects.desktopWindow.Close()
            };
            document.addEventListener('mousedown', (event) => {
              const target = event.target;
              if (!target || !target.closest) return;
              if (!target.closest('.window-chrome')) return;
              if (target.closest('button')) return;
              chrome.webview.postMessage('drag-window');
            }, true);
        ");
        webView.CoreWebView2.Navigate(url);
    }

    public void BeginDrag()
    {
        NativeMethods.ReleaseCapture();
        NativeMethods.SendMessage(Handle, 0xA1, new IntPtr(2), IntPtr.Zero);
    }

    private void ApplyRoundedCorners()
    {
        if (WindowState == FormWindowState.Maximized)
        {
            Region = null;
            return;
        }

        int radius = 12;
        using (GraphicsPath path = new GraphicsPath())
        {
            Rectangle bounds = new Rectangle(0, 0, Width, Height);
            int diameter = radius * 2;
            path.AddArc(bounds.Left, bounds.Top, diameter, diameter, 180, 90);
            path.AddArc(bounds.Right - diameter, bounds.Top, diameter, diameter, 270, 90);
            path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(bounds.Left, bounds.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            Region = new Region(path);
        }
    }
}

[ComVisible(true)]
[ClassInterface(ClassInterfaceType.AutoDual)]
// Expose only native window-chrome actions to the borderless WebView shell.
public sealed class WindowBridge
{
    private readonly Form form;

    public WindowBridge(Form form)
    {
        this.form = form;
    }

    public void Minimize()
    {
        form.BeginInvoke(new MethodInvoker(delegate { form.WindowState = FormWindowState.Minimized; }));
    }

    public bool ToggleMaximize()
    {
        bool maximized = form.WindowState == FormWindowState.Maximized;
        form.BeginInvoke(new MethodInvoker(delegate
        {
            form.WindowState = maximized ? FormWindowState.Normal : FormWindowState.Maximized;
        }));
        return !maximized;
    }

    public void Close()
    {
        form.BeginInvoke(new MethodInvoker(delegate { form.Close(); }));
    }

    public void Drag()
    {
        form.BeginInvoke(new MethodInvoker(delegate
        {
            AppWindow appWindow = form as AppWindow;
            if (appWindow != null)
            {
                appWindow.BeginDrag();
            }
        }));
    }
}

internal static class NativeMethods
{
    [DllImport("user32.dll")]
    internal static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    internal static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);
}
