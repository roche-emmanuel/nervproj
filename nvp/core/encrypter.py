"""Encrypter utility functions"""
import logging

from Crypto.Cipher import PKCS1_OAEP

# cf. https://gist.github.com/YannBouyeron/c5367809904a682767669b6a51f03aa3
from Crypto.PublicKey import RSA

import nvp.core.utils as utl
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return Encrypter(ctx)


class Encrypter(NVPComponent):
    """Encrypter component used to send automatic messages ono Encrypter server"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        # Get the config for this component:
        # self.config = ctx.get_config()["encrypter"]
        # self.public_key = self.config['public_key']
        self.private_key = None
        self.public_key = None

    def generate_keys(self, size, write_key):
        """Generate a pair of RSA keys"""
        logger.info("Generating keys of size %d...", size)
        # pub_key, priv_key = rsa.newkeys(size)
        priv_key = RSA.generate(size)
        pub_key = priv_key.publickey()
        # pub_hex = utl.bytes_to_hex(pub_key.save_pkcs1())
        # priv_hex = utl.bytes_to_hex(priv_key.save_pkcs1())

        pub_str = pub_key.export_key()
        priv_str = priv_key.export_key()
        # pub_str = pub_key.save_pkcs1()
        # priv_str = priv_key.save_pkcs1()
        pub_b64 = utl.bytes_to_b64(pub_str)
        priv_b64 = utl.bytes_to_b64(priv_str)

        # pub_2 = utl.b64_to_bytes(pub_b64)
        # priv_2 = utl.b64_to_bytes(priv_b64)
        # self.check(pub_2 == pub_str, "Mismatch in pub key: %s != %s", pub_2, pub_str)
        # self.check(priv_2 == priv_str, "Mismatch in priv key: %s != %s", priv_2, priv_str)

        # logger.info("Public key:\n%s", pub_key.save_pkcs1().decode('utf-8'))

        logger.info("Public key:\n%s", pub_b64)
        logger.info("Private key:\n%s", priv_b64)

        # Find the home folder:
        home_dir = self.ctx.get_home_dir()
        if self.is_windows:
            home_dir = self.ctx.get_win_home_dir()

        if write_key:
            key_file = self.get_path(home_dir, ".nvp_key")
            if self.file_exists(key_file):
                logger.warning("Key file %s already exists, cancelling write.", key_file)
            else:
                logger.info("Writting key file %s", key_file)
                self.write_text_file(priv_b64, key_file)
                self.set_chmod(key_file, "700")

        logger.info("Done.")

    def get_private_key(self, as_b64=False):
        """Read our private key"""
        if self.private_key is None:
            home_dir = self.ctx.get_home_dir()
            if self.is_windows:
                home_dir = self.ctx.get_win_home_dir()
            key_file = self.get_path(home_dir, ".nvp_key")

            self.check(self.file_exists(key_file), "Cannot read key file %s", key_file)
            content = self.read_text_file(key_file)
            priv_str = utl.b64_to_bytes(content)
            self.private_key = RSA.import_key(priv_str)

        if as_b64:
            return utl.bytes_to_b64(self.private_key.export_key())

        return self.private_key

    def get_public_key(self, as_b64=False):
        """Get the public key"""
        if self.public_key is None:
            priv = self.get_private_key()
            self.public_key = priv.publickey()

        if as_b64:
            return utl.bytes_to_b64(self.public_key.export_key())

        return self.public_key

    def encrypt(self, msg):
        """Encrypt a given message"""
        pub = PKCS1_OAEP.new(self.get_public_key())
        return utl.bytes_to_b64(pub.encrypt(msg.encode("utf-8")))

    def decrypt(self, msg):
        """Decrypt a given message"""
        priv = PKCS1_OAEP.new(self.get_private_key())
        return priv.decrypt(utl.b64_to_bytes(msg)).decode("utf-8")

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "gen-keys":
            size = self.get_param("key_size")
            # logger.info("Should generate key of size %d", size)
            self.generate_keys(size, True)
            return True

        if cmd == "show-pub":
            pub = self.get_public_key(True)
            logger.info("Public key is:\n%s", pub)
            return True

        if cmd == "encrypt":
            msg = self.get_param("message")
            emsg = self.encrypt(msg)
            logger.info("Encrypted:\n%s", emsg)
            return True

        if cmd == "decrypt":
            emsg = self.get_param("message")
            msg = self.decrypt(emsg)
            logger.info("Decrypted:\n%s", msg)
            return True

        return False


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("encrypter", Encrypter(context))

    context.define_subparsers("main", {"gen-keys": None, "show-pub": None, "encrypt": None, "decrypt": None})

    psr = context.get_parser("main.gen-keys")
    psr.add_argument("-s", "--size", dest="key_size", type=int, default=2048, help="Specify the size of the rsa keys.")
    psr = context.get_parser("main.encrypt")
    psr.add_argument("message", type=str, help="Message to encrypt")
    psr = context.get_parser("main.decrypt")
    psr.add_argument("message", type=str, help="Message to decrypt")

    comp.run()
