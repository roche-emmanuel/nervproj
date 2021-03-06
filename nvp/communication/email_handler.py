"""Email utility functions"""
import email
import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return EmailHandler(ctx)


class EmailHandler(NVPComponent):
    """EmailHandler component used to send automatic messages ono rocketchat server"""

    def __init__(self, ctx: NVPContext):
        """Email handler constructor"""
        NVPComponent.__init__(self, ctx)

        # Get the config for this component:
        self.config = ctx.get_config().get("email", None)

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "send":
            msg = self.get_param("message")
            assert msg is not None, "Invalid email message."
            title = self.get_param("title", None)
            to_addrs = self.get_param("to_addrs", None)
            from_addr = self.get_param("from_addr", None)

            self.send_message(title, msg, to_addrs, from_addr)
            return True

        return False

    def send_message(self, title, message, to_addrs=None, from_addr=None, username=None, password=None):
        """Method used to send an email with a given SMTP server"""
        logger.debug("Should send the email message %s", message)

        if self.config is None:
            logger.error("No configuration provided for email_handler: cannot send email:\n%s", message)
            return

        # assert self.config is not None, "No configuration provided for rocketchat."

        if to_addrs is None:
            to_addrs = self.config["default_to_addrs"]
        if from_addr is None:
            from_addr = self.config["default_from_addr"]
        if username is None:
            username = self.config["default_username"]
        if password is None:
            password = self.config["default_password"]

        smtp_server = self.config["smtp_server"]

        # Build the message:
        msg = MIMEMultipart("alternative")

        msg["Subject"] = Header(title, "utf-8")
        msg["From"] = from_addr
        msg["To"] = to_addrs
        msg["Message-id"] = email.utils.make_msgid()
        msg["Date"] = email.utils.formatdate(localtime=True)
        # logger.info("Using date: %s", msg['Date'])

        msg.attach(MIMEText(message.encode("utf-8"), "html", "utf-8"))
        try:
            server = smtplib.SMTP(smtp_server)
            # server = smtplib.SMTP_SSL('smtp.gmail.com')
            server.ehlo()
            server.starttls()
            server.login(username, password)
            # msg = MIMEText(msg.encode('utf-8'), 'html','utf-8')
            # server.sendmail(fromAddr, [toAddr], str(msg))

            server.send_message(msg)
            server.quit()
        except smtplib.SMTPHeloError as err:
            logger.error("No helo greeting: %s", err)
        except smtplib.SMTPAuthenticationError as err:
            logger.error("SMTP authentification error: %s", err)
        except smtplib.SMTPNotSupportedError as err:
            logger.error("SMTP auth not supported: %s", err)
        except smtplib.SMTPException as err:
            logger.error("SMTP exception occured: %s", err)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("email", EmailHandler(context))

    context.define_subparsers(
        "main",
        {
            "send": None,
        },
    )

    psr = context.get_parser("main.send")
    psr.add_argument("message", type=str, help="HTML message that should be sent by email")
    psr.add_argument("-t", "--title", type=str, help="Message title")
    psr.add_argument("-d", "--dest", type=str, dest="to_addrs", help="Destination addresses")
    psr.add_argument("-f", "--from", type=str, dest="from_addr", help="From address")

    comp.run()
