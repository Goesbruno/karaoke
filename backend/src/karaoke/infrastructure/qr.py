def qr_svg(text: str) -> bytes:
    import qrcode, qrcode.image.svg
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    import io
    buf = io.BytesIO(); img.save(buf)
    return buf.getvalue()

def qr_ascii(text: str) -> str:
    import io, qrcode
    q = qrcode.QRCode(border=1); q.add_data(text); q.make(fit=True)
    buf = io.StringIO(); q.print_ascii(out=buf, invert=True)
    return buf.getvalue()
