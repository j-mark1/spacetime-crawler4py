import sqlite3

# The display_ics_subdomains() function goes through the unique_pages database and returns the
# unique subdomains under the ics.uci.edu domain and the frequency count of each subdomain
# as a results_ics_subdomains.txt file.
def display_ics_subdomains():
    conn = sqlite3.connect("unique_pages.db")
    cursor = conn.cursor()

    # Select subdomain column from unique_pages table. When selecting from subdomain column, choose values
    # that end in ".ics.uci.edu"s and group rows in the subdomain column that have the same values (same subdomain)
    # into single, unique rows. For the count column, count the number of subdomains per group. Each group 
    # (unique subdomain) now has a corresponding frequency count. Return results of (subdomain, frequency) in ascending order.
    cursor.execute("""
        SELECT subdomain, COUNT(subdomain) AS frequency
        FROM unique_pages
        WHERE subdomain LIKE '%.ics.uci.edu'
        GROUP BY subdomain
        ORDER BY subdomain ASC
    """)
    conn.commit()

    # Fix http and https subdomains being separate
    http_subdomains = {}
    subdomain_rows = []
    skip = []

    for row in cursor.fetchall():
        if "https" not in row[0]:
            subdomain_rows.append(row)
            # Remove http:// in the beginning to be used to compare just subdomain, store index of that subdomain url
            http_subdomains[row[0].replace("http://", "")] = len(subdomain_rows) - 1
        else: 
            # https subdomain
            subdomain = row[0].replace("https://", "")

            # If there is an http that has https subdomain, store index to know to skip it
            # when writing to file since http redirects to https anyways.
            # Otherwise just add https version to list and move on
            if subdomain in http_subdomains:
                http_index = http_subdomains[subdomain]
                skip.append(http_index)

                # Combine http and https counts 
                row = (row[0], row[1] + subdomain_rows[http_index][1])
            subdomain_rows.append(row)

    with open("results_ics_subdomains.txt", "w", encoding="utf-8") as f:
        for i, row in enumerate(subdomain_rows):
            if i not in skip:
                # Turn the whole row into string types and combine into one string with ", " between each individual string
                row_text = ", ".join(map(str, row))
                f.write(row_text + "\n")

    conn.close()

# The display_unique_pages() function goes through the unique_pages database and returns all
# the pages in the database as (url, subdomain, count). It also returns the sum of all urls found
# (the urls added are unique, thus being the same as the sum of unique pages) as a results_unique_pages.txt file.
def display_unique_pages():
    conn = sqlite3.connect("unique_pages.db")
    cursor = conn.cursor()

    with open("results_unique_pages.txt", "w", encoding="utf-8") as f:
        cursor.execute("""
            SELECT COUNT(*) FROM unique_pages
        """)
        conn.commit()

        f.write(", ".join(map(str, cursor.fetchall()[0])))
        f.write("\n")

        cursor.execute("""
            SELECT * FROM unique_pages
        """)
        conn.commit()

        for row in cursor.fetchall():
            # Turn the whole row into string types and combine into one string with ", " between each individual string
            row_text = ", ".join(map(str, row))
            f.write(row_text + "\n")

    conn.close()

# This processor extracts data from the sqllite database of unique pages into readable text files.
#
# What information is provided?
# Using the unique_pages database, this program provides a list of unique pages found and the summed count for the report.
# Additionally, it determines whether a subdomain is under the ics.uci.edu domain and adds the unique subdomain 
# pages to return the (subdomain, frequency) for the report as well.
if __name__ == "__main__":
    display_unique_pages()
    display_ics_subdomains()