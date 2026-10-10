using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

internal static class InstallerBootstrap
{
    [STAThread]
    private static int Main()
    {
        string tempRoot = Path.Combine(Path.GetTempPath(), "MarkdownToPdfStudio-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tempRoot);
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("app-payload.zip"))
            {
                if (payload == null)
                    throw new InvalidOperationException("The application payload is missing from this installer.");
                string archivePath = Path.Combine(tempRoot, "app-payload.zip");
                using (FileStream output = File.Create(archivePath))
                    payload.CopyTo(output);
                ZipFile.ExtractToDirectory(archivePath, tempRoot);
            }

            using (Stream installScriptResource = Assembly.GetExecutingAssembly().GetManifestResourceStream("install.ps1"))
            {
                if (installScriptResource == null)
                    throw new InvalidOperationException("The installer script is missing from this installer.");
                using (FileStream output = File.Create(Path.Combine(tempRoot, "install.ps1")))
                    installScriptResource.CopyTo(output);
            }

            string installScript = Path.Combine(tempRoot, "install.ps1");
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + installScript + "\"",
                UseShellExecute = false,
                CreateNoWindow = false
            };
            using (Process process = Process.Start(startInfo))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Markdown to PDF Studio setup failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        finally
        {
            try { Directory.Delete(tempRoot, true); }
            catch { }
        }
    }
}
