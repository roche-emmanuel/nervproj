"""CVBuilder handling component

This component is used to generate a CV document from a given yaml description"""
import logging
from io import BytesIO

from cv.styles import define_cv_styles
from odf import draw, table, text
from odf.opendocument import OpenDocumentText
from PIL import Image, ImageDraw

from nvp.admin.cv_builder_base import CVBuilderBase
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class CVBuilder(CVBuilderBase):
    """CVBuilder component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        CVBuilderBase.__init__(self, ctx)
        self.doc = None
        self.styles = {}

        self.colors = {
            "address": (153, 153, 153),
            "infos": (51, 51, 51),
            "highlight": (0, 110, 184),
            "text": (0, 0, 0),
            "grey": (170, 170, 170),
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
        web = self.desc["website"]

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
        self.add_text(txt, f" {self.desc['phone']}")

        self.add_text(txt, " · ")
        self.add_icon(txt, "envelope", "9pt", self.colors["infos"])
        self.add_text(txt, f" {self.desc['email']}")

        self.add_text(txt, " · ")
        self.add_icon(txt, "globe", "9pt", self.colors["infos"])
        self.add_text(txt, " ")
        self.add_link(txt, f"{web['name']}", web["url"])

        # self.add_text(txt, f" {self.desc['website']}")

        # content = f"☏ {self.desc['phone']} | ✉ {self.desc['email']}"
        # txt = text.P(text=content, stylename="InfosStyle")
        parent.addElement(txt)

        txt = text.P(stylename="InfosStyle")
        parent.addElement(txt)

        social = self.desc["social"]
        num = len(social)

        for idx, sname in enumerate(list(social.keys())):
            sdesc = social[sname]
            self.add_brand_icon(txt, sname, "9pt", self.colors["infos"])
            self.add_text(txt, " ")
            self.add_link(txt, f"{sdesc['name']}", sdesc["url"])
            if idx < (num - 1):
                self.add_text(txt, " | ")

        txt = text.P(stylename="InfosStyle")
        parent.addElement(txt)
        # language: f1ab
        self.add_icon(txt, "\uf1ab", "9pt", self.colors["infos"])

        langs = self.desc["languages"]
        lnames = list(langs.keys())
        num = len(lnames)

        for idx, lname in enumerate(lnames):
            self.add_text(txt, f" {lname}: ")
            self.add_text(txt, f" {langs[lname]}", stylename="LanguageStyle")
            if idx < (num - 1):
                self.add_text(txt, " |")

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

        mask_radius = min(image.width, image.height) // 2  # Adjust the radius to control the roundness of corners
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

    def write_mission_section(self, tbl, mission, pcell1, pcell2):
        """Write a mission section"""

        if pcell1 is None:
            row = self.add_row(tbl, stylename="MainTableRow")
            cell1 = self.add_cell(row, stylename="DefaultCellStyle")
            cell2 = self.add_cell(row, stylename="VCenteredCellStyle")
        else:
            cell1 = pcell1
            cell2 = pcell2

        self.write_duration_elements(cell1, mission["from"], mission["to"])

        client = mission["client"]

        txt = text.P(text=f"Client: {client}", stylename="MissionClientStyle")
        cell1.addElement(txt)

        projname = mission["project"]
        pos = mission["position"]

        desc = mission[self.desc_field]
        if isinstance(desc, str):
            desc = [desc]

        techs = mission["techs"].split(",")

        # Add a table for the project/position line:
        ptable = self.add_table(cell2, 2)
        subrow = self.add_row(ptable)

        proj_cell = self.add_cell(subrow)
        txt = text.P(text="", stylename="MissionProjectStyle")
        proj_cell.addElement(txt)

        if "url" in mission:
            self.add_link(txt, f"{projname}", mission["url"])
            # self.add_text(txt, " ")
            # self.add_icon(txt, "\uf0c1", "6pt", self.colors["highlight"]) # link
            # self.add_icon(txt, "\uf08e", "6pt", self.colors["highlight"]) # square with arrow
        else:
            self.add_text(txt, f"{projname}")

        pos_cell = self.add_cell(subrow)
        txt = text.P(text=f"{pos}", stylename="MissionPositionStyle")
        pos_cell.addElement(txt)

        txt = text.P(text="", stylename="MainText")
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

        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # Add a place holder paragraph on the left side:
        txt = self.add_p(cell1, stylename="JobTitlePlaceHolderStyle")

        employer = jobdesc["employer"]
        from_t = self.format_date(jobdesc["from"])
        to_t = self.format_date(jobdesc["to"])
        pos = jobdesc["position"]

        txt = self.add_p(cell2, stylename="JobStyle")
        content = f"{employer} · {pos} · {from_t} - {to_t}"
        self.add_text(txt, content)

        # Now write the missions at this post:
        pcell1 = cell1
        pcell2 = cell2
        for mis in jobdesc["missions"]:
            self.write_mission_section(tbl, mis, pcell1, pcell2)
            pcell1 = None
            pcell2 = None

    def create_main_table(self):
        """Create a main table container"""
        tbl = table.Table(stylename="MainTableStyle")
        self.doc.text.addElement(tbl)

        tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
        tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))

        return tbl

    def write_work_experience(self, tbl=None):
        """Write the work experience sections"""

        if tbl is None:
            tbl = self.create_main_table()

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # txt = text.P(text="Work Experience", stylename="LeftTitle")
        # cell1.addElement(txt)
        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: briefcase: f0b1
        self.add_icon(txt, "\uf0b1", "12pt", self.colors["highlight"])
        self.add_text(txt, " Work Experience")

        self.draw_hline(self.add_p(cell2))

        # Get the work sections:
        for jobdesc in self.desc["work_experience"]:
            self.write_job_section(tbl, jobdesc)

        return tbl

    def write_duration_elements(self, cell, from_date, to_date):
        """Write the duration element in the given cell"""
        from_t = self.format_date(from_date)
        to_t = self.format_date(to_date)

        dur = self.compute_month_duration(from_date, to_date) + 1

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
        cell.addElement(txt)
        txt = text.P(text=dur_str, stylename="MissionDateStyle")
        cell.addElement(txt)

    def write_project_section(self, tbl, proj):
        """Write a project description section"""
        row = self.add_row(tbl, stylename="MainTableRow")

        cell1 = self.add_cell(row, stylename="DefaultCellStyle")

        self.write_duration_elements(cell1, proj["from"], proj["to"])

        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        projname = proj["project"]

        desc = proj[self.desc_field]
        if isinstance(desc, str):
            desc = [desc]

        techs = proj["techs"].split(",")

        # Add a table for the project/position line:
        ptable = self.add_table(cell2, 2)
        subrow = self.add_row(ptable)

        proj_cell = self.add_cell(subrow)
        txt = text.P(text=f"{projname}", stylename="MissionProjectStyle")
        proj_cell.addElement(txt)

        self.add_cell(subrow)
        # txt = text.P(text=f"{pos}", stylename="MissionPositionStyle")
        # pos_cell.addElement(txt)

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

    def write_personal_projects(self, tbl=None):
        """Write the personal project sections"""

        if tbl is None:
            tbl = self.create_main_table()

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # txt = text.P(text="Personal Projects", stylename="LeftTitle")
        # cell1.addElement(txt)
        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: flask: f0c3
        self.add_icon(txt, "\uf0c3", "12pt", self.colors["highlight"])
        self.add_text(txt, " Personal Projects")

        self.draw_hline(self.add_p(cell2))

        # Get the work sections:
        for proj in self.desc["personal_projects"]:
            self.write_project_section(tbl, proj)

        return tbl

    def write_education_section(self, tbl, edu):
        """Write education section"""
        row = self.add_row(tbl, stylename="MainTableRow")

        cell1 = self.add_cell(row, stylename="DefaultCellStyle")

        self.write_duration_elements(cell1, edu["from"], edu["to"])

        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        school = edu["school"]
        qual = edu["qualification"]

        desc = edu["description"]
        if isinstance(desc, str):
            desc = [desc]

        # Add a table for the project/position line:
        ptable = self.add_table(cell2, 2)
        subrow = self.add_row(ptable)

        proj_cell = self.add_cell(subrow)
        txt = text.P(text=f"{school}", stylename="MissionProjectStyle")
        proj_cell.addElement(txt)

        pos_cell = self.add_cell(subrow)
        txt = text.P(text=f"{qual}", stylename="MissionPositionStyle")
        pos_cell.addElement(txt)

        txt = text.P(text=f"", stylename="MainText")
        cell2.addElement(txt)
        num = len(desc)
        for idx, elem in enumerate(desc):
            self.add_text(txt, "- " + elem)
            if idx < (num - 1):
                self.add_linebreak(txt)

    def write_education(self, tbl=None):
        """Write the education section"""

        settings = self.desc["settings"]

        if settings.get("break_on_education", False):
            tbl = table.Table(stylename="MainTableWithBreakStyle")
            self.doc.text.addElement(tbl)
            tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
            tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))
        elif tbl is None:
            tbl = self.create_main_table()

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: graduation-cap: f19d
        self.add_icon(txt, "\uf19d", "12pt", self.colors["highlight"])
        self.add_text(txt, " Education and Training")
        self.draw_hline(self.add_p(cell2))

        # Get the work sections:
        for edu in self.desc["education"]:
            self.write_education_section(tbl, edu)

        return tbl

    def write_additional_skills(self, tbl=None):
        """Write the additional skills section"""

        settings = self.desc["settings"]

        if settings.get("break_on_other_skills", False):
            tbl = table.Table(stylename="MainTableWithBreakStyle")
            self.doc.text.addElement(tbl)
            tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
            tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))
        elif tbl is None:
            tbl = self.create_main_table()

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: screwdriver-wrench: f7d9
        self.add_icon(txt, "\uf7d9", "12pt", self.colors["highlight"])
        self.add_text(txt, " Other Skills")
        self.draw_hline(self.add_p(cell2))

        row = self.add_row(tbl, stylename="MainTableRow")

        self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # Make a list of skills:
        txt = text.P(text="", stylename="MainText")
        cell2.addElement(txt)
        skills = self.desc["additional_skills"]
        snames = list(skills.keys())
        num = len(snames)

        for idx, sname in enumerate(snames):
            self.add_text(txt, "- " + sname + ": ", stylename="LanguageStyle")
            self.add_text(txt, skills[sname])

            if idx < (num - 1):
                self.add_linebreak(txt)

    def write_interests(self, tbl=None):
        """Write the interests section"""

        if tbl is None:
            tbl = self.create_main_table()

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: heart: f004
        self.add_icon(txt, "\uf004", "12pt", self.colors["highlight"])
        self.add_text(txt, " Interests")
        self.draw_hline(self.add_p(cell2))

        row = self.add_row(tbl, stylename="MainTableRow")

        self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # Make a list of skills:
        txt = text.P(text="", stylename="MainText")
        cell2.addElement(txt)
        interests = self.desc["personal_interests"]
        snames = list(interests.keys())
        num = len(snames)

        for idx, sname in enumerate(snames):
            self.add_text(txt, "- " + sname + ": ", stylename="LanguageStyle")
            self.add_text(txt, interests[sname])

            if idx < (num - 1):
                self.add_linebreak(txt)

    def write_skill_elements(self, cell, elems):
        """Write all the skill elements in a given cell"""

        # Get the number of columns:
        settings = self.desc["settings"]
        ncols = settings["num_skill_columns"]
        nsteps = settings["num_skill_steps"]
        pad = settings["skill_step_padding"]
        spacing = settings["skill_step_spacing"]

        # Compute the width of one cell in centimeters
        cwidth = self.page_width * (1.0 - self.left_col_ratio) / ncols

        # Compute the size of each step in centimeters:
        stepw = (cwidth - 2 * pad - (nsteps - 1) * spacing) / nsteps
        # logger.info("Skill step size is: %.4fcm", stepw)

        tbl = self.add_table(cell, ncols=1)

        # Create the Elem style if needed:
        for sname, level in elems.items():

            # For each skill category we add an element:
            row = self.add_row(tbl, stylename="MainTableRow")
            cell = self.add_cell(row, stylename="DefaultCellStyle")

            txt = self.add_p(cell, stylename="SkillElemStyle")
            self.add_text(txt, sname)
            # Add the line representing the level:
            lvl_p = self.add_p(cell, stylename="SkillLineParagraphStyle")
            xpos = pad
            # Draw all the elements:
            for i in range(nsteps):
                suffix = f"{i}" if level >= (i / nsteps) else "Def"
                line = draw.Line(
                    stylename=self.get_style(f"SkillLineStyle{suffix}"),
                    # anchortype="as-char",
                    anchortype="paragraph",
                    zindex=0,
                    x1=f"{xpos:.6f}cm",
                    y1="0.1cm",
                    x2=f"{xpos+stepw:.6f}cm",
                    y2="0.1cm",
                )
                lvl_p.addElement(line)
                xpos += stepw + spacing

    def write_skills(self, tbl=None):
        """Write the skills"""
        settings = self.desc["settings"]

        if settings.get("break_on_skills", False):
            tbl = table.Table(stylename="MainTableWithBreakStyle")
            self.doc.text.addElement(tbl)
            tbl.addElement(table.TableColumn(stylename="MainTableCol0Style"))
            tbl.addElement(table.TableColumn(stylename="MainTableCol1Style"))
        elif tbl is None:
            tbl = self.create_main_table()

        parent_tbl = tbl

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # txt = text.P(text="Work Experience", stylename="LeftTitle")
        # cell1.addElement(txt)
        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: gears: f085
        self.add_icon(txt, "\uf085", "12pt", self.colors["highlight"])
        self.add_text(txt, " Main Skills")

        self.draw_hline(self.add_p(cell2))

        # get the skills categories:
        skills = self.desc["skills"]
        ncols = settings["num_skill_columns"]

        # Add a new big cell:
        row = self.add_row(tbl, stylename="MainTableRow")

        self.add_cell(row, stylename="DefaultCellStyle")
        parent_cell = self.add_cell(row, stylename="DefaultCellStyle")
        # parent_cell = self.add_cell(row, numbercolumnsspanned=2)
        # TableCell(numberrowsspanned=2, numbercolumnsspanned=3)

        # Add a table with the number of target columns in this big parent cell:
        tbl = self.add_table(parent_cell, ncols=ncols)

        # For each skill category we add an element:
        row = self.add_row(tbl, stylename="MainTableRow")
        # cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        # cell2 = self.add_cell(row, stylename="VCenteredCellStyle")
        cat_idx = 0

        for cname, elems in skills.items():
            if cat_idx == ncols:
                # Got to next row:
                cat_idx = 0
                row = self.add_row(tbl, stylename="MainTableRow")

            cell = self.add_cell(row, stylename="DefaultCellStyle")

            txt = self.add_p(cell, stylename="SkillCatStyle")
            self.add_text(txt, cname)

            # write all the elements:
            self.write_skill_elements(cell, elems)

            cat_idx += 1

        return parent_tbl

    def write_cover_letter(self):
        """Write the cover letter for this job"""

        if "cover_letter" not in self.app_desc:
            # Nothing to write here
            return False

        tbl = self.create_new_document(document_type="Cover Letter")

        # Add another row
        row = self.add_row(tbl, stylename="MainTableRow")
        cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # txt = text.P(text="Work Experience", stylename="LeftTitle")
        # cell1.addElement(txt)
        txt = text.P(text="", stylename="LeftTitle")
        cell1.addElement(txt)
        # fa: enveloppe: f0e0
        self.add_icon(txt, "\uf0e0", "12pt", self.colors["highlight"])
        self.add_text(txt, " Cover Letter")

        self.draw_hline(self.add_p(cell2))

        # Read cover letter:
        content = self.app_desc["cover_letter"]

        row = self.add_row(tbl, stylename="MainTableRow")

        # self.add_cell(row, stylename="DefaultCellStyle")
        pcell = self.add_cell(row, stylename="DefaultCellStyle", numbercolumnsspanned=2)

        self.add_p(pcell, text="", stylename="CoverLetterStyle")
        self.add_p(pcell, text="Dear recruiter,", stylename="CoverLetterStyle")
        # self.add_p(pcell, text="", stylename="CoverLetterStyle")

        for line in content:
            self.add_p(pcell, text=line, stylename="CoverLetterStyle")

        fname = self.desc["first_name"]
        lname = self.desc["last_name"]
        lname = lname[0] + lname[1:].lower()
        self.add_p(pcell, text="", stylename="CoverLetterStyle")
        self.add_p(pcell, text="Sincerely,", stylename="CoverLetterRightStyle")
        # self.add_p(pcell, text=f"", stylename="CoverLetterStyle")
        self.add_p(pcell, text=f"{fname} {lname}.", stylename="CoverLetterRightStyle")

        self.save_document("_letter")

    def convert_to_pdf(self, odt_file):
        """Convert the given odt file to pdf with unoconv"""
        # Check here if the writer path is specified:
        if "writer_path" not in self.desc["settings"]:
            logger.info("LibreOffice writer path not provided: not generating pdf file.")
            return

        folder = self.get_parent_folder(odt_file)
        pdf_file = self.set_path_extension(odt_file, ".pdf")

        cwd = self.get_cwd()
        # cmd = ["unoconv", "-f", "pdf", "-o", pdf_file, odt_file]
        # writer_path = "D:/LiberKey/Apps/LibreOffice/LibreOfficeLKL.exe"
        writer_path = self.desc["settings"]["writer_path"]

        cmd = [writer_path, "--headless", "--convert-to", "pdf", odt_file, "--outdir", folder]
        res, rcode, outs = self.execute(cmd, cwd=cwd)

        if not res:
            logger.error("convert command %s (in %s) failed with return code %d:\n%s", cmd, cwd, rcode, outs)
            self.throw("Detected pdf convert failure.")

        logger.info("Done writting %s.", pdf_file)

    def create_new_document(self, **kwargs):
        """Start creating a new document"""

        # Create a new document
        doc = OpenDocumentText()
        self.doc = doc

        # Define the styles:
        define_cv_styles(self, kwargs)

        tbl = self.create_main_table()

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
        _cell1 = self.add_cell(row, stylename="DefaultCellStyle")
        cell2 = self.add_cell(row, stylename="VCenteredCellStyle")

        # txt = text.P(text="Job Applied For", stylename="LeftTitle")
        # cell1.addElement(txt)

        # txt = text.P(text=self.desc["job_applied_for"], stylename="ApplyingPositionStyle")
        txt = text.P(text="", stylename="ApplyingPositionStyle")
        if "job_applied_for" in self.app_desc:
            self.add_text(txt, "Applying to position: ", stylename="ApplyHeaderStyle")
            self.add_text(txt, self.app_desc["job_applied_for"])
            cell2.addElement(txt)

        return tbl

    def write_cv(self):
        """Write the CV content"""

        tbl = self.create_new_document()

        # Add the work experience section:
        self.write_work_experience()

        # Add the personal projects:
        self.write_personal_projects()

        # Add the education section:
        self.write_education()

        # Next we build the skill sections:
        self.write_skills()

        self.write_additional_skills()

        self.write_interests()

        self.save_document("_cv")

    def save_document(self, suffix):
        """Save an odt document and generate the pdf too"""

        # Save the CV to a file
        filename = self.desc["settings"]["filename"]
        odt_file = filename + suffix + ".odt"
        self.doc.save(odt_file)

        logger.info("Done writing %s", odt_file)

        # Also convert the file to pdf here:
        self.convert_to_pdf(odt_file)

    def build(self, cv_file):
        """This function is used build the CV from the given description"""

        self.desc = self.read_yaml(cv_file)

        if "application" in self.desc:
            # Try to read the application file:
            folder = self.get_parent_folder(cv_file)
            app_cfg_file = self.get_path(folder, "applications", self.desc["application"] + ".yml")
            self.app_desc = self.read_yaml(app_cfg_file)

        # Write Curriculum Vitae:
        self.write_cv()

        # Write the cover letter:
        self.write_cover_letter()

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("CVBuilder", CVBuilder(context))

    psr = context.build_parser("build")
    psr.add_str("-i", "--input", dest="input_file")("Input CV yaml config file to use")
    psr.add_flag("-s", "--short", dest="short_version")(
        "Generate short version using overviews instead of descriptions"
    )

    comp.run()
