# Pipe Class: This class functions as a customizable pipeline.
# It can be adapted to work with any external or internal models,
# making it versatile for various use cases outside of just OpenAI models.
from pydantic import BaseModel
from typing import Optional, Union, Generator, Iterator
import pandas as pd

import os
import requests
import json
import gc


class Pipe:
    class Valves(BaseModel):
        OCR_API_BASE_URL: str = "http://jibity-doctr:8080/"
        OCR_API_KEY: str = "your-key"
        pass

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves()
        # self.pipes = self.get_openai_models()
        pass

    def request_ocr_page(self, file_list, page_num):
        """Process a single page of the PDF"""
        headers = {}

        params = {
            "det_arch": "linknet_resnet50",
            "reco_arch": "vitstr_base",
            "pg_start": page_num,
            "pg_end": page_num,
        }

        # Construct file path: /app/backend/data/uploads/{file_id}_{filename}
        file_id = file_list[0]["id"]
        filename = file_list[0]["file"]["filename"]
        file_path = f"/app/backend/data/uploads/{file_id}_{filename}"

        files = [
            (
                "files",
                (
                    os.path.basename(file_list[0]["name"]),
                    open(file_path, "rb"),
                    "application/pdf",
                ),
            ),
        ]

        response = requests.post(
            "http://jibity-doctr:8080/ocr/", params=params, files=files, headers=headers
        )

        assert response.status_code == 200
        json_response = response.json()
        return json_response

    def bin_tab_level(self, df) -> pd.DataFrame:
        """
        Assign tab levels based on closest bin to x-coordinate for lines matching patterns:
        - 2 digits + space + letter (e.g., "03 Fish")
        - 4 digits + space + letter (e.g., "1888 Taxonomic")
        Other lines get tab_level = -1
        """
        if df is None or df.empty:
            return df

        import re

        # Define bin centers
        bins = [0.2649, 0.3016, 0.3395, 0.3761, 0.4120]
        bin_labels = ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]

        # Initialize tab_level columns
        df["tab_level"] = -1
        df["tab_level_binned"] = "No Level"

        # Pattern for 2 digits + space + letter OR 4 digits + space + letter
        pattern = r"^(\d{2}|\d{4})\s+[A-Za-z]"

        for idx, row in df.iterrows():
            text = row.get("text", "")
            geometry = row.get("geometry", [])

            # Check if text matches the pattern
            if re.match(pattern, text.strip()):
                # Extract x-coordinate (first value in geometry)
                if geometry and len(geometry) > 0:
                    x_coord = geometry[0]

                    # Find closest bin
                    closest_bin_idx = min(
                        range(len(bins)), key=lambda i: abs(bins[i] - x_coord)
                    )

                    # Assign tab level (0-4) and label
                    df.at[idx, "tab_level"] = closest_bin_idx
                    df.at[idx, "tab_level_binned"] = bin_labels[closest_bin_idx]

        return df

    def extract_requirement_id(self, simplified_lines):
        """
        Extract Requirement ID from simplified lines.
        Looks for pattern like "Requirement ld: 65568 Version: 7"

        Args:
            simplified_lines: List of line dictionaries

        Returns:
            str: Requirement ID if found, None otherwise
        """
        import re

        for line in simplified_lines:
            text = line.get("text", "").strip()
            # Look for "Requirement ld: <number>" or "Requirement Id: <number>"
            match = re.search(r"Requirement\s+[Il]d?:\s*(\d+)", text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def flatten_hs_codes(self, df, stream_callback=None) -> list:
        """
        Flatten HS codes by building a hierarchical stack and processing tab level 4 entries:
        1. Find first line with tab_level = 0 that starts with a number, push to stack
        2. Continue reading until tab_level = 1 that starts with a number, push to stack
        3. Repeat until tab_level = 3
        4. Continue reading until tab_level = 4, save the whole line
        5. Read subsequent rows with tab_level < 0 and append them
        6. When tab_level >= 0 is found, prepend stack contents and print

        Args:
            df: DataFrame with tab_level column

        Returns:
            list: Processed entries with hierarchical context
        """
        if df is None or df.empty:
            return []

        import re

        stack = []
        target_level = 0
        max_stack_level = 3
        processed_entries = []

        # Pattern to match text starting with a number
        number_pattern = r"^(\d+)"

        # Convert dataframe to list for easier iteration with index tracking
        df_rows = df.to_dict("records")
        i = 0

        while i < len(df_rows):
            row = df_rows[i]
            tab_level = row.get("tab_level", -1)
            text = row.get("text", "").strip()

            # Phase 1: Build stack (levels 0-3)
            if target_level <= max_stack_level and tab_level == target_level:
                # Check if text starts with a number
                match = re.match(number_pattern, text)
                if match:
                    number = match.group(1)
                    stack.append(number)
                    target_level += 1

            # Phase 2: Process tab level 4 and subsequent negative levels
            elif len(stack) == 4 and tab_level == 4:
                # Save the whole line for tab level 4
                level_4_content = text
                i += 1  # Move to next row

                # Read subsequent rows with tab_level < 0
                while i < len(df_rows):
                    next_row = df_rows[i]
                    next_tab_level = next_row.get("tab_level", -1)
                    next_text = next_row.get("text", "").strip()

                    if next_tab_level < 0:
                        # Append negative level content
                        level_4_content += " " + next_text
                        i += 1
                    else:
                        # Found tab_level >= 0, stop collecting and process
                        break

                # Prepend stack contents joined by periods
                stack_prefix = ".".join(stack)
                final_entry = f"{stack_prefix}.{level_4_content}"
                processed_entries.append(final_entry)

                # Stream the processed entry if callback provided
                if stream_callback:
                    # stream_callback(f"{final_entry}")
                    stream_callback(".")
                else:
                    print(f"Processed entry: {final_entry}")

                # Handle stack adjustment for the next iteration
                if i < len(df_rows):
                    current_row = df_rows[i]
                    current_tab_level = current_row.get("tab_level", -1)
                    current_text = current_row.get("text", "").strip()

                    # Check if the current row starts with a number
                    match = re.match(number_pattern, current_text)
                    if match:
                        number = match.group(1)

                        # Adjust stack based on tab level
                        if current_tab_level == 3:
                            # Pop stack once (remove level 3) and push new number
                            stack = stack[:3]  # Keep levels 0,1,2
                            stack.append(number)
                            tab_level = 3
                        elif current_tab_level == 2:
                            # Pop stack twice (remove levels 2,3) and push new number
                            stack = stack[:2]  # Keep levels 0,1
                            stack.append(number)
                            tab_level = 2
                        elif current_tab_level == 1:
                            # Pop stack 3 times (remove levels 1,2,3) and push new number
                            stack = stack[:1]  # Keep level 0
                            stack.append(number)
                            tab_level = 1
                        elif current_tab_level == 0:
                            # Pop stack 4 times (clear stack) and push new number
                            stack = [number]  # Start fresh with new level 0
                            tab_level = 0

                        # Update target_level for next iteration
                        target_level = len(stack)

                # Continue from current position (don't increment i again)
                continue

            i += 1

        return processed_entries

    def process_dataframe(self, df, stream_callback=None):
        """Process the DataFrame to extract insights or perform analysis"""
        if df is None or df.empty:
            return "No data available for analysis."

        # Apply tab level binning
        df = self.bin_tab_level(df)

        # Flatten HS codes and process entries
        processed_entries = self.flatten_hs_codes(df, stream_callback)

        pd.set_option("display.max_columns", None)
        print(f"Dataframe head:\n{df.head(20)}")
        print(f"Processed hierarchical entries: {len(processed_entries)}")

        total_words = len(df)
        avg_confidence = df["confidence"].mean() if "confidence" in df.columns else 0

        summary = f"Total words detected: {total_words}\nAverage confidence: {avg_confidence:.2f}\n"
        summary += f"Processed hierarchical entries: {len(processed_entries)}\n"

        if processed_entries:
            summary += "Hierarchical entries:\n"
            for i, entry in enumerate(processed_entries, 1):
                summary += f"{entry}\n"

        return summary

    def simplify_ocr_to_lines(self, ocr_response):
        """
        Simplify OCR response by merging words on the same line in correct order
        Uses the leftmost word's geometry as the line geometry

        Args:
            ocr_response: The OCR JSON response

        Returns:
            List of dictionaries with line-level data
        """
        try:
            simplified_lines = []

            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]

                if "items" in page_data:
                    for item_idx, item in enumerate(page_data["items"]):
                        if "blocks" in item:
                            for block_idx, block in enumerate(item["blocks"]):
                                if "lines" in block:
                                    for line_idx, line in enumerate(block["lines"]):
                                        if "words" in line and line["words"]:
                                            # Sort words by x-coordinate for correct reading order
                                            sorted_words = sorted(
                                                line["words"],
                                                key=lambda w: w.get("geometry", [0])[0]
                                                if w.get("geometry")
                                                else 0,
                                            )

                                            # Extract word texts and confidences
                                            word_texts = []
                                            word_confidences = []

                                            for word in sorted_words:
                                                if "value" in word:
                                                    word_texts.append(word["value"])
                                                    word_confidences.append(
                                                        word.get("confidence", 0)
                                                    )

                                            # Use leftmost word's geometry as line geometry
                                            leftmost_word = sorted_words[0]
                                            line_geometry = leftmost_word.get(
                                                "geometry", []
                                            )

                                            # Create simplified line data
                                            line_data = {
                                                "text": " ".join(word_texts),
                                                "confidence": sum(word_confidences)
                                                / len(word_confidences)
                                                if word_confidences
                                                else 0,
                                                "geometry": line_geometry,
                                                "item_id": item_idx,
                                                "block_id": block_idx,
                                                "line_id": line_idx,
                                                "word_count": len(word_texts),
                                            }

                                            simplified_lines.append(line_data)

            # Combine lines with similar y-coordinates (within 0.001)
            if simplified_lines:
                simplified_lines = self._combine_similar_y_lines(simplified_lines)

            return simplified_lines

        except Exception as e:
            print(f"Error simplifying OCR response: {e}")
            return []

    def _combine_similar_y_lines(self, lines, y_threshold=0.002):
        """
        Combine lines that have similar y-coordinates (likely same line of text)

        Args:
            lines: List of line dictionaries
            y_threshold: Maximum difference in y-coordinate to consider lines as same

        Returns:
            List of combined line dictionaries
        """
        if not lines:
            return lines

        # Sort lines by y-coordinate first
        sorted_lines = sorted(
            lines,
            key=lambda x: x["geometry"][1]
            if x["geometry"] and len(x["geometry"]) > 1
            else 0,
        )

        combined_lines = []
        current_group = [sorted_lines[0]]

        for i in range(1, len(sorted_lines)):
            current_line = sorted_lines[i]
            previous_line = sorted_lines[i - 1]

            # Get y-coordinates (second value in geometry)
            current_y = (
                current_line["geometry"][1]
                if current_line["geometry"] and len(current_line["geometry"]) > 1
                else 0
            )
            previous_y = (
                previous_line["geometry"][1]
                if previous_line["geometry"] and len(previous_line["geometry"]) > 1
                else 0
            )

            # If y-coordinates are within threshold, add to current group
            if abs(current_y - previous_y) <= y_threshold:
                current_group.append(current_line)
            else:
                # Finalize current group and start new group
                combined_line = self._merge_line_group(current_group)
                combined_lines.append(combined_line)
                current_group = [current_line]

        # Don't forget the last group
        if current_group:
            combined_line = self._merge_line_group(current_group)
            combined_lines.append(combined_line)

        return combined_lines

    def _merge_line_group(self, line_group):
        """
        Merge a group of lines with similar y-coordinates into a single line
        Sort by x-coordinate and combine text
        """
        if len(line_group) == 1:
            return line_group[0]

        # Sort by x-coordinate (leftmost first)
        sorted_group = sorted(
            line_group,
            key=lambda x: x["geometry"][0]
            if x["geometry"] and len(x["geometry"]) > 0
            else 0,
        )

        # Combine text with spaces
        combined_text_parts = []
        total_word_count = 0
        confidence_sum = 0
        confidence_count = 0

        for line in sorted_group:
            if line["text"].strip():
                combined_text_parts.append(line["text"].strip())
            total_word_count += line["word_count"]
            confidence_sum += line["confidence"] * line["word_count"]
            confidence_count += line["word_count"]

        # Use leftmost line's geometry and metadata
        base_line = sorted_group[0]

        return {
            "text": " ".join(combined_text_parts),
            "confidence": confidence_sum / confidence_count
            if confidence_count > 0
            else 0,
            "geometry": base_line["geometry"],
            "item_id": base_line["item_id"],
            "block_id": base_line["block_id"],
            "line_id": base_line["line_id"],
            "word_count": total_word_count,
        }

    def ocr_to_dataframe(self, simplified_lines):
        """
        Convert simplified line data to a pandas DataFrame

        Args:
            simplified_lines: List of dictionaries from simplify_ocr_to_lines()

        Returns:
            pandas.DataFrame with line-level data
        """
        try:
            if not simplified_lines:
                return pd.DataFrame()

            # Convert list of dictionaries directly to DataFrame
            df = pd.DataFrame(simplified_lines)

            return df

        except Exception as e:
            print(f"Error converting simplified lines to DataFrame: {e}")
            return pd.DataFrame()

    def parse_page_range(self, body):
        """Extract start and end page numbers from the message content"""
        try:
            # Get the user message content
            messages = body.get("messages", [])
            if not messages:
                return 1, 1

            user_message = None
            for msg in messages:
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            if not user_message:
                return 1, 1

            # Parse "start: 1 , end: 2" format
            start_page = 1
            end_page = 1

            # Look for start: and end: patterns
            import re

            start_match = re.search(r"start:\s*(\d+)", user_message, re.IGNORECASE)
            end_match = re.search(r"end:\s*(\d+)", user_message, re.IGNORECASE)

            if start_match:
                start_page = int(start_match.group(1))
            if end_match:
                end_page = int(end_match.group(1))

            # Ensure valid range
            if start_page < 1:
                start_page = 1
            if end_page < start_page:
                end_page = start_page

            return start_page, end_page

        except Exception as e:
            print(f"Error parsing page range: {e}")
            return 1, 1

    def extract_text_from_ocr(self, ocr_response):
        """Extract all text from the OCR response structure"""
        try:
            extracted_text = []

            # Handle the list structure from the OCR response
            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]  # Get first (and usually only) page

                # Navigate through: items -> blocks -> lines -> words -> value
                if "items" in page_data:
                    for item in page_data["items"]:
                        if "blocks" in item:
                            for block in item["blocks"]:
                                if "lines" in block:
                                    line_text = []
                                    for line in block["lines"]:
                                        if "words" in line:
                                            word_values = [
                                                word["value"]
                                                for word in line["words"]
                                                if "value" in word
                                            ]
                                            line_text.append(" ".join(word_values))
                                    extracted_text.append(" ".join(line_text))

            return "\n".join(extracted_text)

        except Exception as e:
            print(f"Error extracting text from OCR response: {e}")
            return ""

    def count_ocr_elements(self, ocr_response):
        """Count the number of text blocks/elements in the OCR response"""
        try:
            count = 0

            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]

                if "items" in page_data:
                    for item in page_data["items"]:
                        if "blocks" in item:
                            count += len(item["blocks"])

            return count

        except Exception as e:
            print(f"Error counting OCR elements: {e}")
            return 0

    def pipe(
        self,
        body: dict,
        __user__: dict,
        # __request__: Request,
        __files__: Optional[list] = None,
        **kwargs,
    ) -> Union[str, Generator, Iterator]:
        # print(f"GCNotifyPIPE body: {body}")
        # This is where you can add your custom pipelines like RAG.
        if "user" in body:
            del body["user"]

        if __files__ is None or len(__files__) == 0:
            return "No files provided for processing"

        def stream_ocr_results():
            filename = __files__[0]["file"]["filename"]
            yield f"📄 **Processing file:** {filename}\n\n"

            try:
                # Parse page range from user message
                start_page, end_page = self.parse_page_range(body)
                total_pages = end_page - start_page + 1

                yield f"📊 **Page range:** Processing pages {start_page} to {end_page} ({total_pages} page{'s' if total_pages > 1 else ''})\n\n"
                yield "🔄 **Status:** Starting page-by-page OCR analysis...\n\n"

                # Dictionary to group pages by Requirement ID
                requirement_groups = {}

                # First pass: Extract OCR data and group by Requirement ID
                page_index = 0
                for page_num in range(start_page, end_page + 1):
                    page_index += 1
                    try:
                        yield f"📄 **Processing page {page_num} ({page_index}/{total_pages})**......"

                        # Step 1: Get OCR response
                        page_response = self.request_ocr_page(__files__, page_num)

                        # Step 2: Simplify to lines
                        simplified_lines = self.simplify_ocr_to_lines(page_response)

                        # Step 3: Extract Requirement ID
                        requirement_id = self.extract_requirement_id(simplified_lines)

                        if requirement_id is None:
                            requirement_id = "unknown"

                        yield f"**Requirement ID:** {requirement_id} ......"

                        # Show preview of lines
                        # for line in simplified_lines[
                        #     5:10
                        # ]:  # Show first 3 lines as preview
                        #     yield f"> {line['text']}\n"
                        # yield "\n"

                        # Step 4: Convert to DataFrame
                        df = self.ocr_to_dataframe(simplified_lines)

                        # Group by requirement ID
                        if requirement_id not in requirement_groups:
                            requirement_groups[requirement_id] = {
                                "pages": [],
                                "dataframes": [],
                                "simplified_lines": [],
                            }

                        requirement_groups[requirement_id]["pages"].append(page_num)
                        if df is not None and not df.empty:
                            requirement_groups[requirement_id]["dataframes"].append(df)
                        requirement_groups[requirement_id]["simplified_lines"].extend(
                            simplified_lines
                        )

                        yield f"✅ {len(df) if df is not None else 0} lines detected\n\n"

                    except Exception as page_error:
                        yield f"⚠️ **Page {page_num} error:** {str(page_error)}\n\n"
                        continue

                yield "---\n\n"
                yield "## 📊 **Processing by Requirement ID**\n\n"

                # Second pass: Process grouped dataframes
                total_processed_entries = 0
                for requirement_id, group_data in requirement_groups.items():
                    yield f"### 🔍 **Requirement ID: {requirement_id}**\n"
                    yield f"**Page Numbers:** {', '.join(map(str, group_data['pages']))}\n"

                    if group_data["dataframes"]:
                        # Concatenate all dataframes for this requirement ID
                        combined_df = pd.concat(
                            group_data["dataframes"], ignore_index=True
                        )
                        yield f"**Combined DataFrame:** {len(combined_df)} total lines\n\n"

                        # Create a list to capture processed entries
                        processed_messages = []

                        def stream_entry(message):
                            processed_messages.append(message)

                        # Process combined dataframe with streaming
                        analysis_summary = self.process_dataframe(
                            combined_df, stream_entry
                        )

                        # Yield captured processed entries
                        for message in processed_messages:
                            yield f"{message}"

                        yield f"\n**Analysis Summary:**\n```\n{analysis_summary}\n```\n\n"

                        total_processed_entries += len(combined_df)

                        # Memory cleanup: Clear processed data for this requirement group
                        combined_df = None
                        processed_messages = None
                        analysis_summary = None
                        group_data["dataframes"].clear()
                        group_data["simplified_lines"].clear()

                        # Force garbage collection to free memory immediately
                        gc.collect()

                        yield f"🧹 **Memory cleanup completed for Requirement ID: {requirement_id}**\n\n"
                    else:
                        yield "**No data available for processing**\n\n"

                yield "---\n\n"
                yield "## 📋 **Processing Complete**\n\n"
                yield f"**Total Requirement IDs:** {len(requirement_groups)}\n"
                yield f"**Total pages processed:** {page_index}\n"
                yield f"**Total lines processed:** {total_processed_entries}\n\n"
                yield "🎉 **All requirements processed successfully!**"

            except Exception as e:
                yield f"❌ **Error occurred:** {str(e)}\n\n"
                yield "Please check the file format and try again."

        return stream_ocr_results()
