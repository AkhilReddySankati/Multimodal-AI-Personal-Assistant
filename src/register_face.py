"""
Build encodings.pkl from the images in data/faces/<person>/.

Fixes vs the original src/register_face.py
------------------------------------------
1. FACES_DIR and ENCODING_FILE were relative to the current working
   directory, while src/recognize_face.py resolves encodings.pkl relative to
   the source file. Running the script from anywhere except the project root
   silently wrote the pickle to the wrong place and recognition then failed
   with "Encoding file not found". Both now resolve against the project root.
2. No main guard, so importing the module ran the whole registration.
3. No error when data/faces was missing or empty - it wrote an empty pickle,
   which makes every later login fail with a confusing message.
4. Images with multiple faces were skipped silently as "multiple faces"; the
   counters now report exactly what happened.
"""

import os
import pickle
import sys

import face_recognition


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FACES_DIR = os.path.join(BASE_DIR, "data", "faces")
ENCODING_FILE = os.path.join(BASE_DIR, "encodings.pkl")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def register_faces(faces_dir=FACES_DIR, output_file=ENCODING_FILE):

    if not os.path.isdir(faces_dir):
        raise FileNotFoundError(
            f"Faces folder not found: {faces_dir}\n"
            "Create data/faces/<person_name>/ and put photos inside."
        )

    known_encodings = []
    known_names = []

    skipped_no_face = 0
    skipped_many_faces = 0

    for person_name in sorted(os.listdir(faces_dir)):

        person_folder = os.path.join(faces_dir, person_name)

        if not os.path.isdir(person_folder):
            continue

        print(f"\nProcessing: {person_name}")

        for image_name in sorted(os.listdir(person_folder)):

            if not image_name.lower().endswith(IMAGE_EXTENSIONS):
                continue

            image_path = os.path.join(person_folder, image_name)

            print(f"  {image_name}")

            try:
                image = face_recognition.load_image_file(image_path)
            except Exception as error:
                print(f"    Could not read image: {error}")
                continue

            locations = face_recognition.face_locations(image)
            encodings = face_recognition.face_encodings(image, locations)

            if len(encodings) == 0:
                print("    No face found - skipped")
                skipped_no_face += 1
                continue

            if len(encodings) > 1:
                print("    Multiple faces found - skipped")
                skipped_many_faces += 1
                continue

            known_encodings.append(encodings[0])
            known_names.append(person_name)

            print("    Registered")

    if not known_encodings:
        raise ValueError(
            "No faces were registered. Check that data/faces/<person>/ "
            "contains clear, single-face photos."
        )

    with open(output_file, "wb") as file:
        pickle.dump(
            {"encodings": known_encodings, "names": known_names},
            file,
        )

    print("\n" + "=" * 40)
    print("Face registration completed")
    print("=" * 40)
    print(f"Registered faces : {len(known_encodings)}")
    print(f"People           : {len(set(known_names))}")
    print(f"Skipped (no face): {skipped_no_face}")
    print(f"Skipped (>1 face): {skipped_many_faces}")
    print(f"Saved to         : {output_file}")

    return known_encodings, known_names


if __name__ == "__main__":

    try:
        register_faces()
    except Exception as error:
        print(f"\nError: {error}")
        sys.exit(1)
