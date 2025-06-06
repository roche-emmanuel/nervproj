"""HTTPS server component"""

import http.server
import logging
import os
import ssl
import threading

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return HttpsServer(ctx)


class HttpsServer(NVPComponent):
    """HttpsServer component"""

    def __init__(self, ctx: NVPContext):
        """Class constructor"""
        NVPComponent.__init__(self, ctx)
        self.compiler = None

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "serve":
            root_dir = self.get_param("root_dir")
            port = self.get_param("port")
            index_file = self.get_param("index_file")
            use_chrome = self.get_param("use_chrome")
            no_ssl = self.get_param("no_ssl")
            if index_file is None:
                index_file = self.get_filename(root_dir) + ".html"
            self.serve_directory(root_dir, port, index_file, use_chrome=use_chrome, use_ssl=not no_ssl)
            return True

        return False

    def gen_ssl_cert(self):
        "Generate the ssl certificate if needed"

        cert_dir = self.get_path(self.ctx.get_root_dir(), "data", "certs")
        self.make_folder(cert_dir)

        pem_file = self.get_path(cert_dir, "nervtech.local.crt")

        # if not self.file_exists(pem_file):
        # logger.info("Generating self-signed SSL certificate for localhost...")
        # tools = self.get_component("tools")
        # openssl_path = tools.get_tool_path("openssl")

        # cmd = "req -new -x509 -days 3650 -nodes -out nervtech.local.crt -keyout nervtech.local_key.crt -subj /CN=localhost".split()
        # cmd = [openssl_path] + cmd

        # self.execute(cmd, cwd=cert_dir)

        self.check(self.file_exists(pem_file), "Invalid %s file", pem_file)

        key_file = self.get_path(cert_dir, "nervtech.local_key.crt")
        return pem_file, key_file

    def serve_directory(self, root_dir, port, index_file, use_chrome=False, use_ssl=True):
        """Serve a given directory"""
        logger.info("Serving directory %s...", root_dir)
        os.chdir(root_dir)  # change the current working directory to the folder to serve

        # Check if we have .wasm files in this folder:
        wasm_files = self.get_all_files(root_dir, exp=r"\.wasm$", recursive=False)
        for wfile in wasm_files:
            in_file = self.get_path(root_dir, wfile)
            logger.info("Found WASM file %s", in_file)

            # check if we have a corresponding wasm.br file:
            brfile = in_file + ".br"
            clevel = self.get_param("compression_level")
            if not self.file_exists(brfile):
                logger.info("Generating %s (clevel=%d)...", brfile, clevel)
                brotli = self.get_component("brotli")
                brotli.compress_file(in_file, brfile, clevel=clevel)
            elif self.get_file_mtime(wfile) > self.get_file_mtime(brfile):
                # The brfile already exists but the wasm file is more recent
                logger.info("Updating %s (clevel=%d)...", brfile, clevel)
                self.remove_file(brfile)
                brotli = self.get_component("brotli")
                brotli.compress_file(in_file, brfile, clevel=clevel)
            else:
                logger.info("%s is OK", brfile)

        class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
            """Simple request handler"""

            def __init__(self, *args, **kwargs):
                """Constructor"""
                super().__init__(*args, directory=root_dir, **kwargs)

            def end_headers(self):
                self.send_my_headers()

                http.server.SimpleHTTPRequestHandler.end_headers(self)

            def send_my_headers(self):
                """Senf my headers"""
                self.send_header("Cross-Origin-Opener-Policy", "same-origin")
                self.send_header("Cross-Origin-Embedder-Policy", "require-corp")

        httpd = http.server.HTTPServer(("localhost", port), MyRequestHandler)

        if use_ssl:
            # Add the ssl layer:
            pem_file, key_file = self.gen_ssl_cert()
            cert = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            cert.load_cert_chain(pem_file, key_file)

            # wrap the server socket with SSL and start the server
            httpd.socket = cert.wrap_socket(httpd.socket, server_side=True)

            # logger.info("Serving at https://localhost:%d/%s", port, index_file)
            if port == 443:
                url = f"https://nervtech.local/{index_file}"
            else:
                url = f"https://nervtech.local:{port}/{index_file}"
        else:
            # **Note**: will also work without SSL if we serve on localhost:
            url = f"http://localhost:{port}/{index_file}"

        logger.info("Serving at %s", url)

        # Open the webbrowser and wait for it:
        # webbrowser.open(url)
        # browser_path = webbrowser.get()
        # logger.info("Default webbrowser path: %s", browser_path.name)
        browser_var = "FIREFOX_PATH" if not use_chrome else "CHROME_PATH"
        browser_path = os.getenv(browser_var)

        # if use_chrome:
        #     # Just start the webpage and the server without monitoring the process:
        #     # cmd = [browser_path, "--new-window", "--incognito", url]
        #     cmd = [browser_path, url]
        #     logger.info("Running command: %s", cmd)
        #     self.execute(cmd, shell=True)
        #     browser_path = None

        if browser_path is not None:
            cmd = [browser_path, url]
            if use_chrome:
                cmd = [browser_path, "--user-data-dir=D:/Temp/test", "--new-window", "--incognito", url]
            logger.info("Running command: %s", cmd)

            def run_server():
                """Run the server"""
                logger.info("Running server...")
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    logger.info("HTTPS server interrupted.")
                logger.info("Done with HTTPS server thread.")

            thread = threading.Thread(target=run_server)
            thread.start()

            self.execute(cmd, shell=True)

            logger.info("Stopping HTTPS server...")
            httpd.shutdown()

            thread.join()

        else:
            # Just run the server with no thread:
            httpd.serve_forever()

        logger.info("Done serving directory.")


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("https", HttpsServer(context))

    psr = context.build_parser("serve")
    psr.add_str("--dir", dest="root_dir")("Root directory to serve")
    psr.add_int("--port", dest="port", default=444)("Port where to serve the directory")
    psr.add_int("-c", "--clevel", dest="compression_level", default=11)("Brotly compression level.")
    psr.add_str("--index", dest="index_file")("Default index file to serve")
    psr.add_flag("--chrome", dest="use_chrome")("Specify that we should use chrome as browser")
    psr.add_flag("--no-ssl", dest="no_ssl")("Disable ssl usage")

    comp.run()
