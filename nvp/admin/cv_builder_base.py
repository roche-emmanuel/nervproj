"""CVBuilderBase handling component

This component is used to generate a CV document from a given yaml description"""
import datetime
import logging
from datetime import datetime
from io import BytesIO

import fontawesome as fa
from odf import draw, table, text
from odf.style import Style
from PIL import Image, ImageDraw, ImageFont

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class CVBuilderBase(NVPComponent):
    """CVBuilderBase component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.doc = None
        self.desc = {}
        self.app_desc = None
        self.styles = {}
        self.colors = {}
        self.desc_field = None
        self.text_size = None
        self.left_col_ratio = None
        # Target page width in centimeters:
        self.page_width = 19.0
        self.ext_count = 0

    def get_text_dimensions(self, text_string, font):
        """Get the dimensions of a text"""
        # https://stackoverflow.com/a/46220683/9263761
        text_width = font.getmask(text_string).getbbox()[2]
        text_height = font.getmask(text_string).getbbox()[3]

        return (text_width, text_height)

    def convert_icon_to_image(self, icon_name, size=32, color="black", fname="solid-900"):
        """Convert a fontawesome icon to an image"""
        font_file = f"fonts/fa-{fname}.ttf"

        # Set the icon and size
        icon = icon_name
        if icon_name in fa.icons:
            icon = fa.icons[icon_name]

        # Load the Font Awesome font
        font = ImageFont.truetype(font_file, size - 6)

        # Calculate the text size and position
        # text_width, text_height = draw.textsize(icon, font=font)
        text_width, text_height = self.get_text_dimensions(icon, font)

        size = max(text_width, text_height) + 6
        # logger.info("Using image size: %d", size)

        # Create a blank image with an alpha channel
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

        # Create a drawing context
        idraw = ImageDraw.Draw(image)

        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2

        # Draw the icon on the image
        idraw.text((text_x, text_y), icon, font=font, fill=color)

        # image.save("icon_image.png", "PNG")

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

    def add_auto_style(self, name, family, **kwargs):
        """Add a new style"""
        style = Style(name=name, family=family, **kwargs)
        self.doc.automaticstyles.addElement(style)

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

    def add_auto_graphic_style(self, name, **kwargs):
        """Add a new style"""
        return self.add_auto_style(name, "graphic", **kwargs)

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

    def add_text(self, parent, txt, **kwargs):
        """Add a text element"""
        span = text.Span(text=txt, **kwargs)
        parent.addElement(span)
        return span

    def add_link(self, parent, txt, link, **kwargs):
        """Add a text element"""
        # xlink:type="simple" xlink:href="https://nervtech.org/"
        #                         text:style-name="Internet_20_link"
        #                         text:visited-style-name="Visited_20_Internet_20_Link">
        elem = text.A(type="simple", href=link, stylename="HyperlinkStyle", visitedstylename="VisitedHyperlinkStyle")
        parent.addElement(elem)
        span = text.Span(text=txt, **kwargs)
        elem.addElement(span)
        return span

    def add_linebreak(self, parent):
        """Add a text line break element"""
        lbreak = text.LineBreak()
        parent.addElement(lbreak)
        return lbreak

    def rgb_lighten(self, rgb, factor):
        """Lighten a color"""
        r, g, b = rgb
        if factor != 0:
            # Lighten the color:
            r = int(r + (255.0 - r) * factor)
            g = int(g + (255.0 - g) * factor)
            b = int(b + (255.0 - b) * factor)
        return (r, g, b)

    def rgb_darken(self, rgb, factor):
        """darken a color"""
        r, g, b = rgb
        if factor != 0:
            # draken the color:
            r = int(r + (0.0 - r) * factor)
            g = int(g + (0.0 - g) * factor)
            b = int(b + (0.0 - b) * factor)
        return (r, g, b)

    def rgb_to_hex(self, rgb, lighten=0.0, darken=0.0):
        """Convert RGB tuple to hexadecimal color code."""
        rgb = self.rgb_lighten(rgb, lighten)
        rgb = self.rgb_darken(rgb, darken)

        r, g, b = rgb
        hex_value = "#{:02x}{:02x}{:02x}".format(r, g, b)
        return hex_value

    def get_current_date(self):
        """Get the current formatted date"""
        # Get the current date
        current_date = datetime.today()

        # Format the date
        day_str = current_date.strftime("%B %d")
        year_str = current_date.strftime("%Y")

        # Add the appropriate suffix to the day
        day_suffix = (
            "th" if 11 <= current_date.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(current_date.day % 10, "th")
        )
        # formatted_date = formatted_date.replace(f" {current_date.day},", f" {current_date.day}{day_suffix},")

        return (day_str, day_suffix, year_str)

    def add_p(self, parent, **kwargs):
        """Add a row to a table"""
        pgraph = text.P(**kwargs)
        parent.addElement(pgraph)
        return pgraph

    def add_row(self, tbl, **kwargs):
        """Add a row to a table"""
        row = table.TableRow(**kwargs)
        tbl.addElement(row)
        return row

    def add_table(self, parent, ncols=None, **kwargs):
        """Add a table"""
        tbl = table.Table(**kwargs)
        parent.addElement(tbl)

        if ncols is None:
            return tbl

        for i in range(ncols):
            tbl.addElement(table.TableColumn())

        return tbl

    def add_cell(self, parent, **kwargs):
        """Add a cell"""
        if "valuetype" not in kwargs:
            kwargs["valuetype"] = "string"
        cell = table.TableCell(**kwargs)
        parent.addElement(cell)
        return cell

    def add_icon(self, parent, iname, width, color):
        """Add a fontawesome icon to an element"""
        img = self.convert_icon_to_image(iname, 256, color, "solid-900")
        span = text.Span()
        parent.addElement(span)
        return self.add_image(span, img, width)

    def add_brand_icon(self, parent, iname, width, color):
        """Add a fontawesome icon to an element"""
        img = self.convert_icon_to_image(iname, 256, color, "brands-400")
        span = text.Span()
        parent.addElement(span)
        return self.add_image(span, img, width)

    def add_image(self, parent, img, width):
        """Add an image to a container"""
        picture = draw.Frame(
            stylename=self.get_style("InlinePhotoStyle"), width=width, height=width, anchortype="as-char", zindex=1
        )
        parent.addElement(picture)

        # Create the image element
        image_bytes = BytesIO()

        # Save the image to the BytesIO object
        img.save(image_bytes, format="PNG")

        # Get the image data as a string
        image_string = image_bytes.getvalue()

        # img_path = self.get_path(self.get_cwd(), self.desc["photo"])
        img_ref = self.doc.addPictureFromString(image_string, "image/png")
        image = draw.Image(href=img_ref)
        picture.addElement(image)

        return parent

    def add_image_file(self, parent, imgfile, width):
        """Add an image to a container"""
        picture = draw.Frame(
            stylename=self.get_style("InlinePhotoStyle"), width=width, height=width, anchortype="as-char", zindex=1
        )
        parent.addElement(picture)

        # Create the image element
        # img_path = self.get_path(self.get_cwd(), self.desc["photo"])
        img_ref = self.doc.addPictureFromFile(imgfile)
        image = draw.Image(href=img_ref)
        picture.addElement(image)

    def build(self, cv_file):
        """Build the CV"""
        raise NotImplementedError("Need to implement build")

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "build":
            file = self.get_param("input_file")
            short = self.get_param("short_version")

            self.desc_field = "overview" if short else "description"
            self.text_size = "8pt" if short else "7.5pt"
            self.left_col_ratio = 0.20 if short else 0.165

            return self.build(file)

        return False

    def format_date(self, dstr):
        """Format a date string in the form 03/2022 to Feb. 2022"""
        parts = dstr.split("/")

        if len(parts) == 1:
            # return this string as is:
            return dstr

        # months short names
        months = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."]
        month_str = months[int(parts[0]) - 1]

        return f"{month_str} {parts[1]}"

    def compute_month_duration(self, date1, date2):
        """Compute the month duration between 2 dates given as MM/YYYY"""
        format_string = "%m/%Y"

        # get the current date:
        cur_date = datetime.now()
        if date1 == "Present":
            date1 = f"{cur_date.month:02d}/{cur_date.year}"
        if date2 == "Present":
            date2 = f"{cur_date.month:02d}/{cur_date.year}"

        # Convert strings to datetime objects
        datetime1 = datetime.strptime(date1, format_string)
        datetime2 = datetime.strptime(date2, format_string)

        # Calculate the number of months between the dates
        months = (datetime2.year - datetime1.year) * 12 + (datetime2.month - datetime1.month)

        return abs(months)  # Return the absolute value to handle reversed order of dates

    def draw_hline(self, parent):
        """Draw an horizontal line"""

        # <draw:line text:anchor-type="paragraph"
        #                         draw:z-index="8" draw:name="Ligne 1" draw:style-name="gr2"
        #                         draw:text-style-name="P1" svg:x1="0.076cm" svg:y1="0.39cm"
        #                         svg:x2="12.63cm" svg:y2="0.374cm">
        #                         <text:p />
        #                     </draw:line>
        line = draw.Line(
            stylename=self.get_style("LineStyle"),
            anchortype="as-char",
            # anchortype="paragraph",
            zindex=0,
            x1="0.01cm",
            y1="0.4cm",
            x2=f"{self.page_width*(0.998 - self.left_col_ratio):.4f}cm",
            y2="0.4cm",
        )
        parent.addElement(line)
        # Create a frame to hold the line
        # frame = draw.Frame(width="100%", height="100%", zindex=0)
        # frame = draw.Frame()

        # # Create the line element
        # line = draw.Line(startx="0", starty="50%", endx="100%", endy="50%", stroke="black", zindex=0)

        # # Add the line to the frame
        # frame.addElement(line)

        # Add the frame to the cell
        # parent.addElement(frame)
