from app.services.excel_reader import ExcelReader


def main():

    reader = ExcelReader(
        "data/test.xlsx"
    )

    products = reader.load()

    print(products[:5])


if __name__ == "__main__":

    main()