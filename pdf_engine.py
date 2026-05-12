from pypdf import PdfReader, PdfWriter
import io
import re
import zipfile

def generate_dynamic_filename(reader):
    """Scans the PDF text to build a filename from its internal metadata."""
    working_no = "UNKNOWN-WORKING"
    season = "UNKNOWN-SEASON"
    lifecycle = "UNKNOWN-LIFECYCLE"
    dates_found = []

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue
            
        match_w = re.search(r"Working\s*#\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        if match_w and working_no == "UNKNOWN-WORKING":
            working_no = match_w.group(1).strip()
            
        match_s = re.search(r"Season\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        if match_s and season == "UNKNOWN-SEASON":
            season = match_s.group(1).strip()
            
        match_l = re.search(r"Lifecycle State\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        if match_l and lifecycle == "UNKNOWN-LIFECYCLE":
            lifecycle = match_l.group(1).strip()
            
        matches_d = re.finditer(r"Date and Time\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        for m in matches_d:
            dates_found.append(m.group(1).strip())

    from datetime import datetime
    latest_date_str = "UNKNOWN-DATE"
    if dates_found:
        parsed_dates = []
        for d_str in dates_found:
            try:
                clean_d = re.sub(r'\s+[A-Z]{3,4}$', '', d_str) 
                dt_obj = datetime.strptime(clean_d, "%d-%b-%y at %H:%M:%S")
                parsed_dates.append((dt_obj, d_str))
            except Exception:
                pass
                
        if parsed_dates:
            parsed_dates.sort(key=lambda x: x[0], reverse=True)
            latest_date_str = parsed_dates[0][1]
        else:
            latest_date_str = dates_found[-1]

    raw_name = f"{working_no}_{season}_{latest_date_str}_{lifecycle}"
    safe_name = re.sub(r'[\\/*?:"<>|]', '-', raw_name)
    
    return safe_name + ".pdf"

def process_pdf(uploaded_file, phrases_to_find):
    """Reads the PDF, filters pages, and returns the result dictionary."""
    reader = PdfReader(uploaded_file)
    dynamic_filename = generate_dynamic_filename(reader)
    writer = PdfWriter()
    pages_kept = 0
    tracking_log = []

    for index, page in enumerate(reader.pages):
        page_text = page.extract_text()
        page_num = index + 1
        action = "Removed"
        matched_phrase = "-"
        
        if page_text:
            page_text_lower = page_text.lower()
            for phrase in phrases_to_find:
                if phrase in page_text_lower:
                    action = "Kept"
                    matched_phrase = phrase
                    writer.add_page(page)
                    pages_kept += 1
                    break 
        
        tracking_log.append({
            "Page": page_num,
            "Action": action,
            "Trigger Phrase": matched_phrase
        })

    output_bytes = None
    if pages_kept > 0:
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_bytes = output_buffer.getvalue()

    return {
        "filename": dynamic_filename,
        "bytes": output_bytes,
        "log": tracking_log,
        "kept": pages_kept,
        "total": len(reader.pages)
    }

def create_zip_archive(files_list):
    """Takes a list of tuples (filename, bytes) and returns a ZIP file buffer."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for fname, fbytes in files_list:
            zip_file.writestr(fname, fbytes)
    return zip_buffer.getvalue()