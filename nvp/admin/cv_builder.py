"""CVBuilder handling component

This component is used to generate a CV document from a given yaml description"""
import logging
from io import BytesIO

import fontawesome as fa
from cv.styles import define_cv_styles
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

        self.colors = {
            "address": (153, 153, 153),
            "infos": (51, 51, 51),
            "highlight": (0, 110, 184),
            "text": (0, 0, 0),
            "darktext": (51, 51, 51),
        }

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

    def write_mission_section(self, tbl, mission):
        """Write a mission section"""
        row = self.add_row(tbl, stylename="MainTableRow")

        cell1 = self.add_cell(row, stylename="DefaultCellStyle")

        from_t = self.format_date(mission["from"])
        to_t = self.format_date(mission["to"])
        dur = self.compute_month_duration(mission["from"], mission["to"]) + 1
        client = mission["client"]

        dur_y = 0
        dur_m = dur
        if dur >= 12:
            dur_y = dur // 12
            dur_m = dur - 12 * dur_y

        dur_parts = []
        if dur_y > 0:
            dur_parts.append(f"{dur_y} year{'s' if dur_y>1 else ''}")
        if dur_m > 0:
            dur_parts.append(f"{dur_m} month{'s' if dur_m>1 else ''}")

        dur_str = ", ".join(dur_parts)

        txt = text.P(text=f"{from_t} - {to_t}", stylename="MissionDateStyle")
        cell1.addElement(txt)
        txt = text.P(text=dur_str, stylename="MissionDateStyle")
        cell1.addElement(txt)
        txt = text.P(text=f"Client: {client}", stylename="MissionClientStyle")
        cell1.addElement(txt)

        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        projname = mission["project"]
        pos = mission["position"]

        desc = mission["description"]
        if isinstance(desc, str):
            desc = [desc]

        techs = mission["techs"].split(",")

        # Add a table for the project/position line:
        ptable = self.add_table(cell2, 2)
        subrow = self.add_row(ptable)

        proj_cell = self.add_cell(subrow)
        txt = text.P(text=f"{projname}", stylename="MissionProjectStyle")
        proj_cell.addElement(txt)

        pos_cell = self.add_cell(subrow)
        txt = text.P(text=f"{pos}", stylename="MissionPositionStyle")
        pos_cell.addElement(txt)

        txt = text.P(text=f"", stylename="MainText")
        cell2.addElement(txt)
        num = len(desc)
        for idx, elem in enumerate(desc):
            self.add_text(txt, "- " + elem)
            if idx < (num - 1):
                self.add_linebreak(txt)

        techs = [tech.strip() for tech in techs]

        txt = text.P(text="", stylename="TechsStyleBase")
        num = len(techs)
        for idx, tech in enumerate(techs):
            self.add_text(txt, tech, stylename="TechsStyle")
            if idx < (num - 1):
                self.add_text(txt, " · ")

        cell2.addElement(txt)

    def write_job_section(self, tbl, jobdesc):
        """Write a Job/employer section"""
        row = self.add_row(tbl, stylename="MainTableRow")
        # Not writting anything in the first cell here:
        self.add_cell(row, stylename="DefaultCellStyle")

        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        employer = jobdesc["employer"]
        from_t = self.format_date(jobdesc["from"])
        to_t = self.format_date(jobdesc["to"])
        pos = jobdesc["position"]

        txt = self.add_p(cell2, stylename="JobStyle")
        content = f"{employer} · {pos} · {from_t} - {to_t}"
        self.add_text(txt, content)

        # Now write the missions at this post:
        for mis in jobdesc["missions"]:
            self.write_mission_section(tbl, mis)

    def write_work_experience(self, tbl):
        """Write the work experience sections"""

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        txt = text.P(text="Work Experience", stylename="LeftTitle")
        cell1.addElement(txt)

        self.draw_hline(self.add_p(cell2))

        # Get the work sections:
        for jobdesc in self.desc["work_experience"]:
            self.write_job_section(tbl, jobdesc)

    def build(self, desc):
        """This function is used build the CV from the given description"""
        filename = desc["filename"]
        odt_file = filename + ".odt"

        # Create a new document
        doc = OpenDocumentText()
        self.doc = doc
        self.desc = desc

        # Define the styles:
        define_cv_styles(self)

        tbl = table.Table(stylename="MainTableStyle")
        self.doc.text.addElement(tbl)

        tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
        tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))

        # border="0.06pt solid black"
        row = self.add_row(tbl, stylename="MainTableRow")

        # First column:
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # Write the photo:
        self.write_photo_infos(cell1)

        # Write the header:
        self.write_profile_infos(cell2)

        # Add another row:
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        txt = text.P(text="Job Applied For", stylename="LeftTitle")
        cell1.addElement(txt)

        txt = text.P(text=self.desc["job_applied_for"], stylename="ApplyingPositionStyle")
        cell2.addElement(txt)

        # Add the work experience section:
        self.write_work_experience(tbl)

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
