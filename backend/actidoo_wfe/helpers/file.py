from io import BytesIO


def create_binary_file(buffer: BytesIO, name):
    with open(name, "wb") as file:
        file.write(buffer.read())
    buffer.seek(0)  # set back to 0, so subsequent calls can use the BytesIO object as expected
