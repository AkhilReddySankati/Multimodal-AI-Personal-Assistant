import os
import pickle

import cv2
import numpy as np
import face_recognition


ENCODING_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "encodings.pkl"
)

TOLERANCE = 0.45


def load_known_faces():
    """Load registered face encodings and names."""

    if not os.path.exists(ENCODING_FILE):
        raise FileNotFoundError(
            f"Encoding file not found: {ENCODING_FILE}"
        )

    with open(ENCODING_FILE, "rb") as file:
        data = pickle.load(file)

    return data["encodings"], data["names"]


def recognize_face(image_path):
    """
    Recognize a person from an image.

    Parameters
    ----------
    image_path : str
        Path to the image containing the face.

    Returns
    -------
    str or None
        Recognized person's name.
        Returns None if the face is unknown.
    """

    try:
        known_encodings, known_names = load_known_faces()

        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return None

        image = cv2.imread(image_path)

        if image is None:
            print("Could not read image.")
            return None

        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        face_locations = face_recognition.face_locations(
            rgb_image
        )

        if not face_locations:
            print("No face detected.")
            return None

        face_encodings = face_recognition.face_encodings(
            rgb_image,
            face_locations
        )

        for face_encoding in face_encodings:

            if len(known_encodings) == 0:
                return None

            distances = face_recognition.face_distance(
                known_encodings,
                face_encoding
            )

            best_index = np.argmin(distances)
            best_distance = distances[best_index]

            if best_distance < TOLERANCE:

                name = str(
                    known_names[best_index]
                ).strip()

                print(
                    f"Recognized: {name} "
                    f"(distance={best_distance:.3f})"
                )

                return name

        print("Unknown person.")
        return None

    except Exception as error:

        print(
            f"Face recognition error: {error}"
        )

        return None


def recognize_from_camera():
    """
    Open webcam and recognize a registered person.

    Returns
    -------
    str or None
        Recognized person's name.
    """

    known_encodings, known_names = load_known_faces()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open webcam.")
        return None

    print("Camera started.")
    print("Look at the camera.")
    print("Press Q to quit.")

    recognized_name = None

    while True:

        success, frame = camera.read()

        if not success:
            print("Could not read webcam frame.")
            break

        # Resize for faster face recognition
        small_frame = cv2.resize(
            frame,
            (0, 0),
            fx=0.25,
            fy=0.25
        )

        rgb_frame = cv2.cvtColor(
            small_frame,
            cv2.COLOR_BGR2RGB
        )

        face_locations = face_recognition.face_locations(
            rgb_frame
        )

        face_encodings = face_recognition.face_encodings(
            rgb_frame,
            face_locations
        )

        for face_encoding, location in zip(
            face_encodings,
            face_locations
        ):

            name = "Unknown"
            best_distance = None

            if len(known_encodings) > 0:

                distances = face_recognition.face_distance(
                    known_encodings,
                    face_encoding
                )

                best_index = np.argmin(distances)
                best_distance = distances[best_index]

                if best_distance < TOLERANCE:

                    name = str(
                        known_names[best_index]
                    ).strip()

                    recognized_name = name

            # Scale coordinates back to original frame
            top, right, bottom, left = location

            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            if name == "Unknown":

                box_color = (0, 0, 255)

            else:

                box_color = (0, 255, 0)

            cv2.rectangle(
                frame,
                (left, top),
                (right, bottom),
                box_color,
                2
            )

            label = name

            if best_distance is not None:
                label = (
                    f"{name} "
                    f"({best_distance:.2f})"
                )

            cv2.putText(
                frame,
                label,
                (left, max(top - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                box_color,
                2
            )

        cv2.imshow(
            "Multimodal AI Assistant - Face Authentication",
            frame
        )

        # Stop when authenticated
        if recognized_name is not None:
            break

        # Press Q
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()

    return recognized_name


if __name__ == "__main__":

    user = recognize_from_camera()

    if user:
        print(
            f"\nAuthenticated user: {user}"
        )
    else:
        print(
            "\nAuthentication failed."
        )