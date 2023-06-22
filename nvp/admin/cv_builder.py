"""CVBuilder handling component

This component is used to generate a CV document from a given yaml description"""

import io
import logging

import fontawesome as fa
from odf import teletype, text
from odf.opendocument import OpenDocumentText
from odf.style import ParagraphProperties, Style, TextProperties
from PIL import Image, ImageDraw, ImageFont

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class CVBuilder(NVPComponent):
    """CVBuilder component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.doc = None
        self.desc = None

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "build":
            file = self.get_param("input_file")

            # Read the configuration:
            cfg = self.read_yaml(file)

            return self.build(cfg)

        return False

    def convert_icon_to_image(self, icon_name, size=32, color="black"):
        """Convert a fontawesome icon to an image"""
        font_file = "fonts/fa-solid-900.ttf"

        # Set the icon and size
        icon = fa.icons[icon_name]

        # Create a blank image with an alpha channel
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

        # Create a drawing context
        draw = ImageDraw.Draw(image)

        # Load the Font Awesome font
        font = ImageFont.truetype(font_file, size - 6)

        # Calculate the text size and position
        text_width, text_height = draw.textsize(icon, font=font)
        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2

        # Draw the icon on the image
        draw.text((text_x, text_y), icon, font=font, fill=color)

        image.save("icon_image.png", "PNG")

        return image

    def build(self, desc):
        """This function is used build the CV from the given description"""
        filename = desc["filename"]
        odt_file = filename + ".odt"

        # Create a new document
        doc = OpenDocumentText()
        self.doc = doc

        # Create a style for the CV heading
        props = ParagraphProperties()
        # logger.info("Allowed paragraphProerties attribs: %s", [el[1] for el in props.allowed_attributes()])

        heading_style = Style(name="Heading", family="paragraph", defaultoutlinelevel="1")
        props = ParagraphProperties(textalign="center")
        # props.setAttribute("text-align", "center")

        heading_text_properties = TextProperties(fontsize="24pt", fontweight="bold")
        heading_style.addElement(props)
        heading_style.addElement(heading_text_properties)
        doc.styles.addElement(heading_style)

        # Add CV heading
        cv_heading = text.P(text="Curriculum Vitae", stylename=heading_style)
        doc.text.addElement(cv_heading)

        # Add personal information
        personal_info = text.H(text="Personal Information", outlinelevel=1)
        doc.text.addElement(personal_info)

        name = text.P(text="Your Name")
        doc.text.addElement(name)

        email = text.P(text="Email: your.email@example.com")
        doc.text.addElement(email)

        phone = text.P(text="Phone: +1 123-456-7890")
        doc.text.addElement(phone)

        # Add education section
        education = text.H(text="Education", outlinelevel=1)
        doc.text.addElement(education)

        # Add your education details (e.g., degree, university, year)
        degree = text.P(text="Degree in XYZ, University of ABC, 20XX")
        doc.text.addElement(degree)

        # Save the CV to a file
        doc.save(odt_file)

        logger.info("Done writing %s", odt_file)
        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("CVBuilder", CVBuilder(context))

    psr = context.build_parser("build")
    psr.add_str("-i", "--input", dest="input_file")("Input CV yaml config file to use")

    comp.run()
