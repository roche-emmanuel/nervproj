"""PDFHandler handling component"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

import PyPDF2

logger = logging.getLogger(__name__)


class PDFHandler(NVPComponent):
    """PDFHandler component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "interleave-pdfs":
            files = self.get_param("input_files").split(",")

            self.merge_pages(files)
            return True
        if cmd == "compress-pdfs":
            files = self.get_param("input_files").split(",")
            inplace = self.get_param("in_place")
            for fname in files:
                self.compress_pdf(fname, inplace)
            return True

    def compress_pdf(self, input_pdf, inplace):
        """Compress a PDF file"""

        pdf_file = open(input_pdf, "rb")
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        pdf_writer = PyPDF2.PdfWriter()

        # Add all pages to the PDF writer
        for _, page in enumerate(pdf_reader.pages):
            page.compress_content_streams()
            pdf_writer.add_page(page)

        pdf_file.close()

        # Save the compressed PDF to the output file
        output_pdf = self.set_path_extension(input_pdf, "_comp.pdf")
        if inplace is True:
            output_pdf = input_pdf

        with open(output_pdf, "wb") as output_file:
            pdf_writer.write(output_file)

    def merge_pages(self, files):
        """Merge the PDF files"""
        logger.info("Merging pdfs...")

        # Open the pdf files:
        pdfs = [PyPDF2.PdfReader(fname) for fname in files]

        # Create a new PDF file to save the merged pages
        merged_pdf = PyPDF2.PdfWriter()

        # Determine the total number of pages in the merged PDF
        max_num_pages = max([len(pdf.pages) for pdf in pdfs])

        # Iterate through the pages and merge them alternately
        for page_num in range(max_num_pages):
            for pdf in pdfs:
                if page_num < len(pdf.pages):
                    merged_pdf.add_page(pdf.pages[page_num])

        # Save the merged PDF to a new file
        with open("merged.pdf", "wb") as output_file:
            merged_pdf.write(output_file)

        logger.info("Written merged.pdf")


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("PDFHandler", PDFHandler(context))

    psr = context.build_parser("interleave-pdfs")
    psr.add_str("-i", "--inputs", dest="input_files")("input files to merge")
    psr = context.build_parser("compress-pdfs")
    psr.add_str("-i", "--inputs", dest="input_files")("input files to compress")
    psr.add_flag("-p", "--inplace", dest="in_place")("Inplace compression")

    comp.run()
