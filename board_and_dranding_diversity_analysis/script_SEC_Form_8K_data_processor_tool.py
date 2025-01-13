# script_SEC_Form_8K_data_processor_tool

import openai
import os
import PyPDF2
import pandas as pd
import csv
import shutil

# Set your OpenAI API key
openai.api_key = 'use you own api key'

# Define the specific path where the board data is stored
base_directory = r'use your own path'

def list_folders(exclude_folder='Extracted'):
        return [
        item for item in os.listdir(base_directory)
        if os.path.isdir(os.path.join(base_directory, item)) and item != exclude_folder
    ]

def read_files_from_directory(directory_path):
    return [os.path.join(directory_path, filename) for filename in os.listdir(directory_path) if filename.endswith('.pdf')]

def move_folder_to_new_directory(source_folder, new_directory=os.path.join(base_directory, 'Extracted')):
    try:
        if os.path.exists(source_folder):
            os.makedirs(new_directory, exist_ok=True)
            shutil.move(source_folder, os.path.join(new_directory, os.path.basename(source_folder)))
            return True
        else:
            print("Source folder does not exist.")
            return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def split_text_into_chunks(text, max_tokens=4096):
    chunks = []
    while len(text) > max_tokens:
        split_point = text.rfind(".", 0, max_tokens)
        if split_point == -1:
            split_point = max_tokens
        chunks.append(text[:split_point + 1])
        text = text[split_point + 1:]
    chunks.append(text)
    return chunks

# migrate to the new API
def extract_data(folder_name):
    folder = os.path.join(base_directory, folder_name)
    input_files = read_files_from_directory(folder)
    output = []

    for file in input_files:
        print(f"Processing: {file}")
        pdf_reader = PyPDF2.PdfReader(file)
        text_content = ''.join(page.extract_text() for page in pdf_reader.pages)

        max_token_limit = 4096
        start_index = text_content.find("Item 5.02")
        if start_index != -1:
            end_index = min(start_index + max_token_limit, len(text_content))
            relevant_text = text_content[start_index:end_index]
        else:
            relevant_text = "Item 5.02 not found in the text."

        messages = [
            {"role": "system", "content": "You are a specialized model trained to extract details from SEC Form 8-K filings."},
            {"role": "user", "content": (
                "Extract Name, Effective date, Role (director, president, etc.), and Change "
                "(e.g., appointment, election, resignation) from the following file. "
                "Limit the Change to 5 words, no commas. "
                "Put only a person's name in the Name column, "
                "and ensure all dates are in yyyy-mm-dd format."
                "Exclude dollar amounts. Give the data in CSV format."
            )}
        ]
        
        relevant_text_chunks = split_text_into_chunks(relevant_text, max_token_limit)
        messages.extend([{"role": "user", "content": chunk} for chunk in relevant_text_chunks])

        # Updated API Call for openai>=1.0.0
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=messages
        )
        
        extracted_information = response['choices'][0]['message']['content']

        # Process CSV-like response
        data = csv.reader(extracted_information.splitlines())
        processed_data = []
        
        for row in data:
            if len(row) > 4:
                merged_column = f'{row[2]}, {row[3]}'
                new_row = row[:2] + [merged_column] + row[4:]
                processed_data.append(new_row)
            else:
                processed_data.append(row)
        
        output.extend(processed_data[1:])

    df = pd.DataFrame(output, columns=['Name', 'Effective Date', 'Role', 'Change'])
    output_file_path = os.path.join(folder, f"{folder_name}.csv")
    df.to_csv(output_file_path, index=False)
    print(f"{output_file_path} saved")

    move_folder_to_new_directory(folder)

folders = list_folders()

for folder in folders:
    extract_data(folder)

