"""ThumbGen handling component

This component is used to generate youtube thumbnails from a given description in yaml"""

import logging
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import distance_transform_edt

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

from rembg import new_session, remove


class ThumbGen(NVPComponent):
    """ThumbGen component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "gen-thumb":
            tagname = self.get_param("tag_name")

            # Get the desc dir:
            desc_dir = os.environ["NV_YT_DESC_DIR"]

            # get the prefix:
            prefix = tagname[:3]
            # cfg_file = self.get_path(self.get_cwd(), "descs", prefix, tagname + ".yml")
            cfg_file = self.get_path(desc_dir, prefix, tagname + ".yml")
            cfg = self.read_yaml(cfg_file)

            # Get the entry from the file:
            desc = cfg["thumbnail"]
            return self.generate_thumbnail(tagname, desc)

        if cmd == "remove-bg":
            in_file = self.get_param("input_file")
            out_file = self.get_param("output_file")
            model = self.get_param("model_name")
            min_dist = self.get_param("min_dist")
            max_dist = self.get_param("max_dist")

            bg_color = self.get_param("bg_color")
            return self.remove_background(in_file, out_file, model, min_dist, max_dist, bg_color)

        return False

    def compute_distance_to_foreground(self, img):
        """Compute the euclidian distance to the 1 elements assuming that 1 is for the forreground"""
        arr = np.array(img)

        binary_arr = np.zeros_like(arr)
        binary_arr[arr < 200] = 1

        # arr.astype(np.bool_).astype(np.uint8)

        # flip 0/1:
        # binary_arr = 1 - binary_arr

        dist = distance_transform_edt(binary_arr)
        return dist

    def remove_background(self, in_file, out_file, model_name, min_dist, max_dist, bg_color):
        """Remove the background from an image file"""
        # Usage infos: https://github.com/roche-emmanuel/rembg/blob/main/USAGE.md

        if out_file is None:
            out_file = self.set_path_extension(in_file, "_nobg.png")

        logger.info("Removing background from %s...", in_file)
        input_img = Image.open(in_file)
        # output_img = remove(input_img)

        # model_name = "u2net"
        # model_name = "isnet-general-use"
        session = new_session(model_name)

        if max_dist != min_dist:
            # Get the mask only:
            mask = remove(input_img, session=session, only_mask=True).convert("L")
            logger.info("Retrieved foreground mask.")

            # Compute the distance to foreground:
            dist = self.compute_distance_to_foreground(mask)

            # Convert the input image to RGBA:
            img = input_img.convert("RGBA")

            img_arr = np.array(img)

            dist = np.clip(dist, min_dist, max_dist)
            alpha = 1.0 - (dist - min_dist) / (max_dist - min_dist)

            # mask_arr = np.array(mask)

            # img_arr[:, :, 3] = (img_arr[:, :, 3].astype(np.float64) * alpha).astype(np.uint8)
            img_arr[:, :, 3] = (255 * alpha).astype(np.uint8)

            # img_arr[:, :, 3] = mask_arr

            # Convert the numpy array back to image:
            output_img = Image.fromarray(img_arr)
        else:
            # Use default processing:
            output_img = remove(input_img, session=session)

        if bg_color is not None:
            col = [np.float32(el) / 255.0 for el in bg_color.split(",")]
            arr = np.array(output_img).astype(np.float32) / 255.0
            colarr = np.zeros_like(arr)
            alpha = arr[:, :, 3]

            for i in range(4):
                colarr[:, :, i] = col[i]

                arr[:, :, i] = arr[:, :, i] * alpha + colarr[:, :, i] * (1.0 - alpha)

            arr = (arr * 255.0).astype(np.uint8)

            output_img = Image.fromarray(arr)

        output_img.save(out_file)
        logger.info("Done removing background.")
        return True

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

    def adjust_tint(self, image, tint_factors):
        """Adjust the tint of an image"""
        # Split the image into its individual color channels (R, G, B)
        r, g, b, a = image.split()

        # Reduce the intensity of the red channel using the tint_factor
        r = r.point(lambda i: i * tint_factors[0])
        g = g.point(lambda i: i * tint_factors[1])
        b = b.point(lambda i: i * tint_factors[2])

        # Merge the adjusted color channels back into a single image
        adjusted_image = Image.merge("RGBA", (r, g, b, a))

        return adjusted_image

    def adjust_brightness(self, image, factor):
        """Adjust the tint of an image"""
        # Create a lambda function to adjust the pixel values
        adjust = lambda value: min(int(value * factor), 255)

        r, g, b, a = image.split()
        r = r.point(adjust)
        g = g.point(adjust)
        b = b.point(adjust)

        # Merge the adjusted color channels back into a single image
        return Image.merge("RGBA", (r, g, b, a))

    def mirror_image_horiz(self, img):
        """Mirror an image horizontally"""
        return img.transpose(Image.FLIP_LEFT_RIGHT)

    def add_images(self, img, idescs):
        """Add "sub-images" on our background image"""

        img_dir = self.get_path(self.get_cwd(), "inputs")

        ref_size = min(img.width, img.height)

        for desc in idescs:
            logger.info("Adding sub image: %s", desc["src"])

            # load the image from source:
            sub_img = Image.open(self.get_path(img_dir, desc["src"]))
            sub_img = sub_img.convert("RGBA")

            # Rescale the image to fit the requested scale:
            tgt_size = ref_size * desc["scale"]

            # compute the scaling factor:
            sfactor = min(tgt_size / sub_img.width, tgt_size / sub_img.height)

            # Resize the image sub_img to the "tgt_size" value keeping the aspect ratio:
            sub_img = sub_img.resize((int(sub_img.width * sfactor), int(sub_img.height * sfactor)))

            if "tint_factors" in desc:
                sub_img = self.adjust_tint(sub_img, desc["tint_factors"])

            if "brightness" in desc:
                sub_img = self.adjust_brightness(sub_img, desc["brightness"])

            if desc.get("mirror", False):
                sub_img = self.mirror_image_horiz(sub_img)

            if "outline_size" in desc:
                # sub_img = ImageOps.expand(sub_img, border=desc["outline_size"], fill=desc["outline_color"])
                alpha = sub_img.split()[3]
                edges = alpha.filter(ImageFilter.FIND_EDGES)
                edges = edges.filter(ImageFilter.MaxFilter(size=desc["outline_size"]))
                edges = edges.convert("L")
                mask = edges.point(lambda p: p > 0 and 255)

                contours = Image.new("RGBA", sub_img.size, (0, 0, 0, 0))
                contours.paste(Image.new("RGBA", sub_img.size, tuple(desc["outline_color"])), mask=mask)

                contours.paste(sub_img, mask=sub_img)
                sub_img = contours

            if "angle" in desc:
                sub_img = sub_img.rotate(desc["angle"], expand=True)

            # Compute center position:
            xpos = int(desc["pos"][0] * img.width) - sub_img.width // 2
            ypos = int(desc["pos"][1] * img.height) - sub_img.height // 2

            img.paste(sub_img, (xpos, ypos), mask=sub_img)
            # img = sub_img

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

    def draw_subtitle(self, img, desc, drawbg):
        """Draw the subtitle of the thumbnail if applicable"""

        fname = "subtitle"
        if fname not in desc:
            # Nothing to do:
            return img

        params = {
            "text": desc[fname],
            "font_file": desc.get(f"{fname}_font", "Doctor Glitch.otf"),
            "font_size": desc.get(f"{fname}_font_size", 56),
            "text_color": desc.get(f"{fname}_color", (255, 255, 255, 255)),
            "rect_color": desc.get(f"{fname}_rect_color", (130, 130, 130, 220)),
            "rect_hpad": desc.get(f"{fname}_rect_hpad", 20),
            "outline_width": desc.get(f"{fname}_outline_size", 4),
            "outline_color": desc.get(f"{fname}_outline_color", (0, 0, 0, 200)),
            "xpos": desc.get(f"{fname}_xpos", 20),
            "ypos": desc.get(f"{fname}_ypos", -40),
            "line_spacing": desc.get(f"{fname}_line_spacing", 10),
            "text_halign": desc.get(f"{fname}_halign", "left"),
            "shadow_offset_x": 8,
            "shadow_offset_y": 8,
        }

        return self.draw_text_overlay(img, params, drawbg)

    def draw_title(self, img, desc, drawbg):
        """Draw the title elements"""

        fname = "title"

        if fname not in desc:
            # Nothing to do:
            return img

        params = {
            "text": desc[fname],
            "font_file": desc.get(f"{fname}_font", "BebasNeue.otf"),
            "font_size": desc.get(f"{fname}_font_size", 160),
            "text_color": desc.get(f"{fname}_color", (255, 255, 0, 255)),
            "rect_color": desc.get(f"{fname}_rect_color", (230, 230, 230, 80)),
            "rect_hpad": desc.get(f"{fname}_rect_hpad", 30),
            "outline_width": desc.get(f"{fname}_outline_size", 5),
            "outline_color": desc.get(f"{fname}_outline_color", (255, 0, 0, 200)),
            "xpos": desc.get(f"{fname}_xpos", 20),
            "ypos": desc.get(f"{fname}_ypos", 40),
            "line_spacing": desc.get(f"{fname}_line_spacing", 10),
            "text_halign": desc.get(f"{fname}_halign", "left"),
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
        }

        return self.draw_text_overlay(img, params, drawbg)

    def get_text_dimensions(self, text_string, font):
        """Get the dimensions of a text"""
        # https://stackoverflow.com/a/46220683/9263761
        # ascent, descent = font.getmetrics()
        # logger.info("ascent: %f, descent: %f", ascent, descent)

        text_width = font.getmask(text_string).getbbox()[2]
        # text_height = font.getmask(text_string).getbbox()[3]
        text_height = font.getmask(text_string).getbbox()[3]
        # logger.info("text_height: %f", text_height)

        return (text_width, text_height)

    def draw_text_overlay(self, img, params, drawbg):
        """Draw a text overlay on the image with an optional background band and outline effect."""

        overlay = Image.new("RGBA", img.size)

        # Create an ImageDraw object
        draw = ImageDraw.Draw(overlay)

        text = params["text"]
        font_file = self.get_path(self.get_input_dir(), "fonts", params["font_file"])
        self.check(self.file_exists(font_file), "Invalid font file %s", font_file)

        # Specify the font style, size, and color
        # font = ImageFont.truetype("arial.ttf", 72)  # Replace "arial.ttf" with the path to your font file
        font = ImageFont.truetype(font_file, params["font_size"])  # Replace "arial.ttf" with the path to your font file

        # Calculate the position to center the text on the image

        # text_width, text_height = draw.textsize(text, font)
        _, text_height = self.get_text_dimensions(text, font)
        # text_bbox = draw.textbbox((0, 0), text, font=font)
        # text_width = text_bbox[2]
        # - text_bbox[0]
        # text_height = text_bbox[3]
        # - text_bbox[1]

        # Draw the background rectangle:
        x = params["xpos"]
        y = params["ypos"]
        line_spacing = params["line_spacing"]

        lines = text.split("\n")
        nlines = len(lines)
        total_text_height = text_height * nlines + line_spacing * (nlines - 1)
        hpad = params["rect_hpad"]
        rect_color = params["rect_color"]
        outline_width = params["outline_width"]
        outline_color = params["outline_color"]
        text_color = params["text_color"]
        text_halign = params["text_halign"]

        if isinstance(rect_color, list):
            rect_color = tuple(rect_color)
        if isinstance(text_color, list):
            text_color = tuple(text_color)
        if isinstance(outline_color, list):
            outline_color = tuple(outline_color)

        rect_height = 2 * hpad + total_text_height

        if y < 0:
            y = img.height + y - total_text_height

        if drawbg:
            draw.rectangle([(0, y - hpad), (img.width, y - hpad + rect_height)], fill=rect_color)
        else:
            anchor = "lt"

            if text_halign == "center":
                x = img.width // 2
                anchor = "mt"
            if text_halign == "right":
                x = img.width - x
                anchor = "rt"

            # x = (img.width - text_width) // 2
            # y = (img.height - text_height) // 2

            # Draw the text outline if applicable:

            # if outline_width > 0:
            #     outline_color = params["outline_color"]

            #     for xo in range(-outline_width, outline_width + 1):
            #         for yo in range(-outline_width, outline_width + 1):
            #             draw.text((x + xo, y + yo), text, font=font, fill=outline_color)

            # Write the text on the image
            # Split the text lines:

            xoff = params["shadow_offset_x"]
            yoff = params["shadow_offset_y"]
            shadow_color = (0, 0, 0, 128)

            for line in lines:
                if xoff != 0 or xoff != 0:
                    # draw the shadow first:
                    draw.text(
                        (x + xoff, y + yoff),
                        line,
                        font=font,
                        fill=shadow_color,
                        stroke_width=0,
                        stroke_fill=None,
                        anchor=anchor,
                    )

                draw.text(
                    (x, y),
                    line,
                    font=font,
                    fill=text_color,
                    stroke_width=outline_width,
                    stroke_fill=outline_color,
                    anchor=anchor,
                )
                y += text_height + line_spacing

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

        # First we draw the background rects:
        img = self.draw_title(img, desc, True)
        img = self.draw_subtitle(img, desc, True)

        # Add the additional images:
        img = self.add_images(img, desc.get("images", []))

        # Write the title if any:
        img = self.draw_title(img, desc, False)

        # Write the subtile if any:
        img = self.draw_subtitle(img, desc, False)

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

    psr = context.build_parser("remove-bg")
    psr.add_str("-i", "--input", dest="input_file")("input image file from which to remove the background")
    psr.add_str("-o", "--output", dest="output_file")("output image file")
    psr.add_str("-m", "--model", dest="model_name", default="u2net")("Name of model to use")
    psr.add_float("--mind", dest="min_dist", default=0.0)("Min falloff dist")
    psr.add_float("--maxd", dest="max_dist", default=5.0)("Max falloff dist")
    psr.add_str("--bgcolor", dest="bg_color")("Background color as coma separated list of U8s")

    comp.run()
