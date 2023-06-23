"""CVBuilder handling component

This component is used to generate a CV document from a given yaml description"""
import logging
from io import BytesIO

import fontawesome as fa
from odf import draw, table, text
from odf.opendocument import OpenDocumentText
from odf.style import (
    GraphicProperties,
    ParagraphProperties,
    Style,
    TableCellProperties,
    TableColumnProperties,
    TableProperties,
    TextProperties,
)
from PIL import Image, ImageDraw, ImageFont

from nvp.admin.cv_builder_base import CVBuilderBase
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class CVBuilder(CVBuilderBase):
    """CVBuilder component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        CVBuilderBase.__init__(self, ctx)
        self.doc = None
        self.desc = None
        self.styles = {}

        self.colors = {"address": (153, 153, 153), "infos": (51, 51, 51), "highlight": (0, 110, 184), "text": (0, 0, 0)}

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

        style = self.add_graphic_style("InlinePhotoStyle", parentstylename="PhotoStyle")
        style.addElement(
            GraphicProperties(
                wrap="parallel",
                wrapcontour="false",
                verticalpos="middle",
                verticalrel="text",
                horizontalpos="from-left",
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
                color=self.rgb_to_hex(self.colors["highlight"]),
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
                color=self.rgb_to_hex(self.colors["address"]),
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
                fontname="Calibri",
                fontfamily="Calibri",
                # fontname="Candara",
                # fontfamily="Candara",
                color=self.rgb_to_hex(self.colors["infos"]),
                # texttransform="uppercase",
                # fontvariant="small-caps",
            )
        )

        style = self.add_paragraph_style("LeftTitle")
        style.addElement(
            ParagraphProperties(
                textalign="right", margintop="0cm", marginbottom="0.cm", marginright="0.3cm", verticalalign="center"
            )
        )
        style.addElement(
            TextProperties(
                fontsize="12pt",
                fontweight="normal",
                fontname="Calibri",
                fontfamily="Calibri",
                color=self.rgb_to_hex(self.colors["highlight"]),
                fontvariant="small-caps",
            )
        )

        style = self.add_paragraph_style("MainText")
        style.addElement(
            ParagraphProperties(
                textalign="left", margintop="0cm", marginbottom="0.0cm", marginleft="0cm", verticalalign="center"
            )
        )
        style.addElement(
            TextProperties(
                fontsize="12pt",
                fontweight="normal",
                fontname="Calibri",
                fontfamily="Calibri",
                color=self.rgb_to_hex(self.colors["text"]),
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

        # img = self.convert_icon_to_image("map-pin", 256, self.colors['address'])
        # img.save("map_pin.png", "PNG")

        txt = text.P(stylename="AddressStyle")
        parent.addElement(txt)
        # self.add_image_file(txt, "map_pin.png", "9pt")
        # self.add_image(txt, img, "9pt")
        # map-location-dot = \uf5a0
        self.add_icon(txt, "\uf5a0", "9pt", self.colors["address"])
        txt.addElement(text.Span(text=" " + self.desc["address"], stylename="AddressStyle"))

        # txt = text.P(text="⚐ " + self.desc["address"], stylename="AddressStyle")
        # parent.addElement(txt)

        txt = text.P(stylename="InfosStyle")
        self.add_icon(txt, "phone", "9pt", self.colors["infos"])
        txt.addElement(text.Span(text=" " + self.desc["phone"] + " "))
        span = text.Span()
        txt.addElement(span)
        self.add_icon(span, "envelope", "9pt", self.colors["infos"])
        txt.addElement(text.Span(text=" " + self.desc["email"]))

        # content = f"☏ {self.desc['phone']} | ✉ {self.desc['email']}"
        # txt = text.P(text=content, stylename="InfosStyle")
        parent.addElement(txt)

        txt = text.P(stylename="InfosStyle")
        parent.addElement(txt)

        self.add_icon(txt, "globe", "9pt", self.colors["infos"])
        self.add_text(txt, f" {self.desc['website']} | ")
        self.add_brand_icon(txt, "github", "9pt", self.colors["infos"])
        self.add_text(txt, f" {self.desc['github']} | ")
        self.add_brand_icon(txt, "linkedin", "9pt", self.colors["infos"])
        self.add_text(txt, f" {self.desc['linkedin']} | ")
        self.add_brand_icon(txt, "twitter", "9pt", self.colors["infos"])
        self.add_text(txt, f" {self.desc['twitter']}")

    def write_photo_infos(self, parent):
        """Write the photo infos"""
        # Create a paragraph to hold the picture
        paragraph = text.P(stylename="VerticalCenterStyle")

        parent.addElement(paragraph)

        # Create the picture element
        picture = draw.Frame(
            stylename=self.get_style("PhotoStyle"), width="3.5cm", height="3.5cm", anchortype="paragraph"
        )
        paragraph.addElement(picture)

        # Start with the input photo:
        image = Image.open(self.desc["photo"])

        # Create a mask with a circular shape
        mask = Image.new("L", image.size, 0)
        idraw = ImageDraw.Draw(mask)
        # mask_center = (image.width // 2, image.height // 2)
        # mask_radius = min(image.width, image.height) // 2
        # idraw.ellipse(
        #     (
        #         mask_center[0] - mask_radius,
        #         mask_center[1] - mask_radius,
        #         mask_center[0] + mask_radius,
        #         mask_center[1] + mask_radius,
        #     ),
        #     fill=255,
        # )

        mask_radius = min(image.width, image.height) // 5  # Adjust the radius to control the roundness of corners
        idraw.rounded_rectangle([(0, 0), image.size], fill=255, radius=mask_radius)

        # Apply the circular mask to the original image
        result = Image.new("RGBA", image.size)
        result.paste(image, (0, 0), mask)

        # Create the image element
        image_bytes = BytesIO()

        # Save the image to the BytesIO object
        result.save(image_bytes, format="PNG")

        # Get the image data as a string
        image_string = image_bytes.getvalue()

        # img_path = self.get_path(self.get_cwd(), self.desc["photo"])
        img_ref = self.doc.addPictureFromString(image_string, "image/png")

        # Create the image element
        # img_path = self.get_path(self.get_cwd(), self.desc["photo"])
        # img_ref = self.doc.addPictureFromFile(self.desc["photo"])
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

        # Write the photo:
        self.write_photo_infos(cell1)

        # Write the header:
        self.write_profile_infos(cell2)

        # Add another row:
        row = table.TableRow()
        tbl.addElement(row)
        cell1 = table.TableCell(stylename="DefaultCellStyle", valuetype="string")
        row.addElement(cell1)
        cell2 = table.TableCell(stylename="VCenteredCellStyle", valuetype="string")
        row.addElement(cell2)

        txt = text.P(text="Job Applied For", stylename="LeftTitle")
        cell1.addElement(txt)

        txt = text.P(text=self.desc["job_applied_for"], stylename="MainText")
        cell2.addElement(txt)

        # Add another row - work experience
        row = table.TableRow()
        tbl.addElement(row)
        cell1 = table.TableCell(stylename="DefaultCellStyle", valuetype="string")
        row.addElement(cell1)
        cell2 = table.TableCell(stylename="VCenteredCellStyle", valuetype="string")
        row.addElement(cell2)

        txt = text.P(text="Work Experience", stylename="LeftTitle")
        cell1.addElement(txt)

        txt = text.P(
            text="------------------------------------------------------------------------", stylename="MainText"
        )
        cell2.addElement(txt)

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
