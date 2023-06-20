"""ThumbGen handling component

This component is used to generate youtube thumbnails from a given description in yaml"""

import logging

from PIL import Image, ImageDraw, ImageFont

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class ThumbGen(NVPComponent):
    """ThumbGen component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "gen-thumb":
            cfg_file = self.get_param("input_file")
            cfg = self.read_yaml(cfg_file)

            # Get the entry from the file:
            tag_name = self.get_param("tag_name")
            desc = cfg[tag_name]
            return self.generate_thumbnail(tag_name, desc)

        return False

    def load_background_image(self, iname):
        """Load a background image"""

        bg_dir = self.get_path(self.get_cwd(), "inputs", "backgrounds")

        ext = self.get_path_extension(iname)
        exts = [".jpg", ".png"]
        if ext == "":
            for ext in exts:
                if self.file_exists(bg_dir, iname + ext):
                    iname = iname + ext
                    break

        # The file should exist:
        self.check(self.file_exists(bg_dir, iname), "Invalid background image %s", iname)

        # load that image:
        img = Image.open(self.get_path(bg_dir, iname))
        return img

    def fill_area(self, img, width, height):
        """Stretch the input image as needed to fill a given area"""

        # Calculate the aspect ratios
        original_width, original_height = img.size
        target_width, target_height = width, height
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height

        # Determine the resize ratio and apply it to the image
        resize_ratio = max(width_ratio, height_ratio)
        new_size = (int(original_width * resize_ratio), int(original_height * resize_ratio))
        resized_image = img.resize(new_size)

        # Create a blank canvas of size 1280x720
        canvas = Image.new("RGBA", (target_width, target_height), "white")

        # Calculate the position to center the resized image on the canvas
        x_offset = (target_width - new_size[0]) // 2
        y_offset = (target_height - new_size[1]) // 2

        # Paste the resized image onto the canvas
        canvas.paste(resized_image, (x_offset, y_offset))

        return canvas

    def get_input_dir(self):
        """Retrieve the input dir"""
        return self.get_path(self.get_cwd(), "inputs")

    def draw_title(self, img, desc):
        """Draw the title elements"""
        overlay = Image.new("RGBA", img.size)

        # Create an ImageDraw object
        draw = ImageDraw.Draw(overlay)

        # Define the text to write
        text = desc["title"]
        font_file = desc.get("title_font", "BebasNeue.otf")
        font_file = self.get_path(self.get_input_dir(), "fonts", font_file)
        self.check(self.file_exists(font_file), "Invalid font file %s", font_file)
        font_size = desc.get("title_font_size", 160)
        text_color = desc.get("title_font_color", (255, 255, 0, 255))

        # Specify the font style, size, and color
        # font = ImageFont.truetype("arial.ttf", 72)  # Replace "arial.ttf" with the path to your font file
        font = ImageFont.truetype(font_file, font_size)  # Replace "arial.ttf" with the path to your font file

        # Calculate the position to center the text on the image
        # text_width, text_height = draw.textsize(text, font)
        text_bbox = draw.textbbox((0, 0), text, font=font)
        # text_width = text_bbox[2]
        # - text_bbox[0]
        text_height = text_bbox[3]
        # - text_bbox[1]

        # Draw the background rectangle:
        x = 20
        y = 10

        rect_color = (230, 230, 230, 128)
        draw.rectangle([(0, y), (img.width, y + text_height + 25)], fill=rect_color)

        # x = (img.width - text_width) // 2
        # y = (img.height - text_height) // 2

        outline_width = desc.get("title_outline_size", 5)
        outline_color = desc.get("title_outline_color", (255, 0, 0, 200))

        # Draw the text outline
        for xo in range(-outline_width, outline_width + 1):
            for yo in range(-outline_width, outline_width + 1):
                draw.text((x + xo, y + yo), text, font=font, fill=outline_color)

        # Write the text on the image
        draw.text((x, y), text, font=font, fill=text_color)

        # Composite the images:
        img.alpha_composite(overlay)

        return img

    def generate_thumbnail(self, tagname, desc):
        """This function is used to generate a thumbnail with the given input settings"""

        # Thumbnail dimensions:
        width = 1280
        height = 720

        logger.info("Input desc: %s", desc)

        # Get the input/output dir:
        out_dir = self.get_path(self.get_cwd(), "outputs")
        self.make_folder(out_dir)

        # write an output file in the output dir:
        out_file = self.get_path(out_dir, f"{tagname}.png")

        # load the background image:
        img = self.load_background_image(desc["background"])
        img = self.fill_area(img, width, height)

        # Write the title if any:
        if "title" in desc:
            img = self.draw_title(img, desc)

        # save the image:
        logger.info("Writing thumbnail: %s", out_file)
        img.save(out_file, "PNG")

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("ThumbGen", ThumbGen(context))

    psr = context.build_parser("gen-thumb")
    # psr.add_flag("-f", "--use-folder-name", dest="use_folder_name")("Rename using parent folder name")
    # psr.add_str("tag_name", nargs="?", default="all")("input file where to read the config settings from")
    psr.add_str("tag_name")("Input tag to generate a thumbnail for")
    psr.add_str("-i", "--input", dest="input_file", default="videos.yml")(
        "input file where to read the config settings from"
    )

    comp.run()
