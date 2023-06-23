"""CVBuilder handling component

This component is used to generate a CV document from a given yaml description"""

import io
import logging

import fontawesome as fa
from odf import draw, table, teletype, text
from odf.opendocument import OpenDocumentText
from odf.style import (
    FontFace,
    GraphicProperties,
    ParagraphProperties,
    Style,
    TableCellProperties,
    TableColumnProperties,
    TableProperties,
    TextProperties,
)
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
        self.styles = {}

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

    def get_style(self, name):
        """Get a style by name"""
        return self.styles[name]

    def add_style(self, name, family, **kwargs):
        """Add a style"""
        style = Style(name=name, family=family, **kwargs)
        self.doc.styles.addElement(style)
        self.styles[name] = style

        return style

    def add_paragraph_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "paragraph", **kwargs)

    def add_text_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "text", **kwargs)

    def add_graphic_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "graphic", **kwargs)

    def add_table_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "table", **kwargs)

    def add_table_column_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "table-column", **kwargs)

    def add_table_cell_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_style(name, "table-cell", **kwargs)

    def add_auto_table_style(self, name, **kwargs):
        """Add a new style"""
        style = Style(name=name, family="table", **kwargs)
        self.doc.automaticstyles.addElement(style)

        return style

    def add_auto_table_column_style(self, name, **kwargs):
        """Add a new style"""
        style = Style(name=name, family="table-column", **kwargs)
        self.doc.automaticstyles.addElement(style)

        return style

    def add_auto_table_cell_style(self, name, **kwargs):
        """Add a new style"""
        style = Style(name=name, family="table-cell", **kwargs)
        self.doc.automaticstyles.addElement(style)

        return style

    def add_text(self, txt, **kwargs):
        """Add a text element"""

        elem = text.P(text=txt, **kwargs)
        self.doc.text.addElement(elem)
        return elem

    def rgb_to_hex(self, rgb):
        """Convert RGB tuple to hexadecimal color code."""
        r, g, b = rgb
        hex_value = "#{:02x}{:02x}{:02x}".format(r, g, b)
        return hex_value

    def define_styles(self):
        """Define the styles we will use in the document"""

        style = self.add_paragraph_style("VerticalCenterStyle")
        style.addElement(ParagraphProperties(verticalalign="center"))

        style = self.add_graphic_style("GraphicsBase")
        style.addElement(
            GraphicProperties(
                anchortype="paragraph",
                x="0cm",
                y="0cm",
                wrap="dynamic",
                numberwrappedparagraphs="nolimit",
                wrapcontour="false",
                verticalpos="top",
                verticalrel="paragraph",
                horizontalpos="center",
                horizontalrel="paragraph",
            )
        )

        style = self.add_graphic_style("PhotoStyle", parentstylename="GraphicsBase")
        style.addElement(
            GraphicProperties(
                wrap="none",
                runthrough="foreground",
                verticalpos="middle",
                verticalrel="paragraph-content",
                horizontalpos="center",
                horizontalrel="paragraph-content",
                mirror="none",
                clip="rect(0cm, 0cm, 0cm, 0cm)",
                luminance="0%",
                contrast="0%",
                red="0%",
                green="0%",
                blue="0%",
                gamma="100%",
                colorinversion="false",
                imageopacity="100%",
                colormode="standard",
            )
        )

        style = self.add_paragraph_style("FirstNameStyle")
        style.addElement(ParagraphProperties(textalign="center", verticalalign="center"))
        style.addElement(
            TextProperties(
                fontsize="32pt", fontweight="normal", fontname="Roboto Condensed", fontfamily="Roboto Condensed"
            )
        )

        style = self.add_text_style("LastNameStyle")
        style.addElement(
            TextProperties(
                fontsize="32pt",
                fontweight="normal",
                fontname="Roboto",
                fontfamily="Roboto",
                color=self.rgb_to_hex((0, 110, 184)),
            )
        )

        style = self.add_paragraph_style("QualificationsStyle")
        style.addElement(
            ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
        )
        style.addElement(
            TextProperties(
                fontsize="7.6pt",
                fontweight="normal",
                fontname="Source Sans Pro",
                fontfamily="Source Sans Pro",
                color=self.rgb_to_hex((0, 110, 184)),
                # texttransform="uppercase",
                fontvariant="small-caps",
            )
        )

        style = self.add_paragraph_style("AddressStyle")
        style.addElement(
            ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
        )
        style.addElement(
            TextProperties(
                fontsize="8pt",
                fontweight="normal",
                fontname="Source Sans Pro",
                fontfamily="Source Sans Pro",
                color=self.rgb_to_hex((153, 153, 153)),
                # texttransform="uppercase",
                fontvariant="small-caps",
            )
        )

        style = self.add_paragraph_style("InfosStyle")
        style.addElement(
            ParagraphProperties(textalign="center", margintop="0cm", marginbottom="0.2cm", verticalalign="center")
        )
        style.addElement(
            TextProperties(
                fontsize="9pt",
                fontweight="normal",
                fontname="Candara",
                fontfamily="Candara",
                color=self.rgb_to_hex((51, 51, 51)),
                # texttransform="uppercase",
                # fontvariant="small-caps",
            )
        )

        # usable page width in centimeters:
        pwidth = 17.0

        style = self.add_auto_table_style("MainTableStyle")
        style.addElement(TableProperties(width="100%", align="margins"))

        # rel1 = (2 ^ 16 - 1) // 4
        # rel2 = ((2 ^ 16 - 1) * 3) // 4
        style = self.add_auto_table_column_style("MainTableCol0Style")
        style.addElement(TableColumnProperties(columnwidth=f"{pwidth/4.0:.2f}cm"))  # , relcolumnwidth=f"{rel1}*"
        style = self.add_auto_table_column_style("MainTableCol1Style")
        style.addElement(TableColumnProperties(columnwidth=f"{pwidth*3.0/4.0:.2f}cm"))  # , relcolumnwidth=f"{rel2}*"

        style = self.add_auto_table_cell_style("DefaultCellStyle")
        style.addElement(TableCellProperties(padding="0cm", border="none"))
        style = self.add_auto_table_cell_style("VCenteredCellStyle")
        style.addElement(TableCellProperties(padding="0cm", border="none", verticalalign="middle"))

    def write_profile_infos(self, parent):
        """Write the profile infos"""

        txt = text.P(text=self.desc["first_name"], stylename="FirstNameStyle")
        txt.addElement(text.Span(text=" " + self.desc["last_name"], stylename="LastNameStyle"))
        parent.addElement(txt)

        content = " · ".join(self.desc["qualifications"])
        txt = text.P(text=content, stylename="QualificationsStyle")
        parent.addElement(txt)

        txt = text.P(text="⚐ " + self.desc["address"], stylename="AddressStyle")
        parent.addElement(txt)

        content = f"☏ {self.desc['phone']} | ✉ {self.desc['email']}"
        txt = text.P(text=content, stylename="InfosStyle")
        parent.addElement(txt)

    def write_photo_infos(self, parent):
        """Write the photo infos"""
        # Create a paragraph to hold the picture
        paragraph = text.P(stylename="VerticalCenterStyle")

        parent.addElement(paragraph)

        # Create the picture element
        picture = draw.Frame(
            stylename=self.get_style("PhotoStyle"), width="3.5cm", height="3.5cm", anchortype="paragraph"
        )

        # picture.setAutomaticStyleName("fr1")
        # picture.setAttribute("draw:name", "Image")
        # picture.setAttribute("svg:width", "5cm")  # Set the desired width
        # picture.setAttribute("svg:height", "5cm")  # Set the desired height
        # picture.setAttribute("draw:z-index", "0")
        # picture.setAttribute("text:anchor-type", "paragraph")
        paragraph.addElement(picture)

        # Create the image element
        # img_path = self.get_path(self.get_cwd(), self.desc["photo"])
        img_ref = self.doc.addPictureFromFile(self.desc["photo"])
        image = draw.Image(href=img_ref)
        picture.addElement(image)

    def build(self, desc):
        """This function is used build the CV from the given description"""
        filename = desc["filename"]
        odt_file = filename + ".odt"

        # Create a new document
        doc = OpenDocumentText()
        self.doc = doc
        self.desc = desc

        # Define the styles:
        self.define_styles()

        tbl = table.Table(stylename="MainTableStyle")
        self.doc.text.addElement(tbl)

        tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
        tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))

        # border="0.06pt solid black"
        row = table.TableRow()
        tbl.addElement(row)

        # First column:
        cell1 = table.TableCell(stylename="DefaultCellStyle", valuetype="string")
        row.addElement(cell1)
        cell2 = table.TableCell(stylename="VCenteredCellStyle", valuetype="string")
        row.addElement(cell2)

        self.write_photo_infos(cell1)

        # txt = text.P(text="This is the first column")
        # cell1.addElement(txt)

        # txt = text.P(text="This is the second column")
        # cell2.addElement(txt)

        # Write the header:
        self.write_profile_infos(cell2)

        # @ ✉ ☏🚩⚐
        # Create a style for the CV heading
        # props = ParagraphProperties()
        # logger.info("Allowed paragraphProerties attribs: %s", [el[1] for el in props.allowed_attributes()])

        # Define a custom font style
        # logger.info("Allowed FontFace attribs: %s", [el[1] for el in FontFace(name="test").allowed_attributes()])
        # font_face = FontFace(name="MyStroke", fontfamily="MyStroke", fontfile="fonts/Stroke.ttf")
        # doc.fontfacedecls.addElement(font_face)

        # font_properties = TextProperties(attributes={"style:font-name": "MyFont"})
        # font_style.addElement(font_properties)
        # doc.styles.addElement(font_style)

        # heading_style = Style(name="Heading", family="paragraph", defaultoutlinelevel="1")
        # props = ParagraphProperties(textalign="center")
        # # props.setAttribute("text-align", "center")

        # heading_text_properties = TextProperties(fontsize="24pt", fontweight="bold", fontname="MyStroke")
        # heading_style.addElement(props)
        # heading_style.addElement(heading_text_properties)
        # doc.styles.addElement(heading_style)

        # # Add CV heading
        # cv_heading = text.P(text="Curriculum Vitae", stylename=heading_style)
        # doc.text.addElement(cv_heading)

        # # Add personal information
        # personal_info = text.H(text="Personal Information", outlinelevel=1)
        # doc.text.addElement(personal_info)

        # name = text.P(text="Your Name")
        # doc.text.addElement(name)

        # email = text.P(text="Email: your.email@example.com")
        # doc.text.addElement(email)

        # phone = text.P(text="Phone: +1 123-456-7890")
        # doc.text.addElement(phone)

        # # Add education section
        # education = text.H(text="Education", outlinelevel=1)
        # doc.text.addElement(education)

        # # Add your education details (e.g., degree, university, year)
        # degree = text.P(text="Degree in XYZ, University of ABC, 20XX")
        # doc.text.addElement(degree)

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
