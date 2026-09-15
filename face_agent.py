import os
import sys


# --------------------------------------------------
# Add src folder to Python path
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SRC_DIR = os.path.join(
    BASE_DIR,
    "src"
)

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# --------------------------------------------------
# Import face recognition functions
# --------------------------------------------------

from recognize_face import recognize_face
from recognize_face import recognize_from_camera


# --------------------------------------------------
# Authentication using image
# --------------------------------------------------

def authenticate_user(image_path):
    """
    Authenticate a user using a face image.

    Returns:
        str: recognized person's name
        None: unknown / failed authentication
    """

    try:

        if not image_path:
            return None

        if not os.path.exists(image_path):
            print(
                f"Image not found: {image_path}"
            )
            return None

        name = recognize_face(
            image_path
        )

        if name is None:
            return None

        if str(name).strip().lower() == "unknown":
            return None

        return str(name).strip()

    except Exception as error:

        print(
            f"Authentication error: {error}"
        )

        return None


# --------------------------------------------------
# Authentication using webcam
# --------------------------------------------------

def authenticate_from_camera():
    """
    Authenticate the user through the webcam.

    Returns:
        str: recognized person's name
        None: unknown / failed authentication
    """

    try:

        name = recognize_from_camera()

        if name is None:
            return None

        if str(name).strip().lower() == "unknown":
            return None

        return str(name).strip()

    except Exception as error:

        print(
            f"Camera authentication error: {error}"
        )

        return None