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
            if index_file is None:
                index_file = self.get_filename(root_dir) + ".html"
            self.serve_directory(root_dir, port, index_file)
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

    def serve_directory(self, root_dir, port, index_file):
        """Serve a given directory"""
        logger.info("Serving directory %s...", root_dir)
        os.chdir(root_dir)  # change the current working directory to the folder to serve

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

        # **Note**: will also work without SSL if we serve on localhost:
        # url = f"http://localhost:{port}/{index_file}"

        logger.info("Serving at %s", url)

        # Open the webbrowser and wait for it:
        # webbrowser.open(url)
        # browser_path = webbrowser.get()
        # logger.info("Default webbrowser path: %s", browser_path.name)
        firefox_path = os.getenv("FIREFOX_PATH")
        if firefox_path is not None:
            cmd = [firefox_path, url]

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
    psr.add_str("--index", dest="index_file")("Default index file to serve")

    comp.run()
