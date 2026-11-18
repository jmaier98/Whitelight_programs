# Measurement procedures

Put one PDF per procedure in this folder (write it in Word, then Save As PDF so the
text can be selected). The agent finds them with `list_procedures` and reads them with
`get_procedure`, so you can ask it to "run the standard reflectivity map" and it will
follow the written steps and compare its results with any reference images.

Start each PDF with a one-sentence summary; that line is what `list_procedures` shows.
Use the exact axis and measurement names from the 2D Scan tab in the steps.

Reading procedures needs PyMuPDF: `pip install pymupdf`.
