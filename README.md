
# Power BI Ingest

A CLI tool to extract schema and measures from Power BI PBIP projects. It parses `.tmdl` files from the project's Semantic Model and outputs either a Mermaid ERD or formatted DAX measure expressions.

## Requirements

- A Power BI project saved in [PBIP format](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview) (`.pbip`)

## Usage

```
pbingest <PROJECT_PATH> [--table] [--measure] [--output <FILE>]
```

| Argument | Description |
|---|---|
| `PROJECT_PATH` | Path to the PBIP project folder (must contain a `.SemanticModel` subfolder) |
| `--table` | Extract all tables with columns and data types, and render relationships as a Mermaid ERD. This is the **default** when no option is specified. |
| `--measure` | Extract all DAX measure expressions, grouped by table. |
| `--output FILE` | Write output to a file instead of stdout. |

Both `--table` and `--measure` can be combined in a single run.

## Examples

- Open the `Revenue Opportunities.pbix` file and save it in PBIP format in the `/pbi_sample_project` directory.

```bash
# Generate ERD diagram (default)
pbingest ./pbi_sample_project

# Generate ERD and save to file
pbingest ./pbi_sample_project --table --output erd.md

# Export all DAX measures
pbingest ./pbi_sample_project --measure --output measures.md

# Generate both ERD and measures in one file
pbingest ./pbi_sample_project --table --measure --output output.md
```

---

## Sample Output

### `--table` — Mermaid ERD

Generated from `pbi_sample_project` (Revenue Opportunities):

```mermaid
erDiagram
    Accounts {
        string Account
        string Region
        string Segment
        int _Account_ID_
        string State
    }
    Dates {
        datetime Date
        int Year
        int Day
        string Month
        string _Day_Of_Week_Name_
        int _Week_of_Year_
        int _Month__Sort_Order__
        int _Day__Sort_Order__
    }
    Opportunities {
        string Name
        int _Opportunity_ID_
        int Rank
        string _Opportunity_Size_
        int _Size__Sort_Order__
    }
    Partners {
        string Partner
        int _Partner_ID_
        string _Partner_Driven_
    }
    Products {
        string _Product_Code_
        int _Product_ID_
    }
    Sales {
        int _Opportunity_ID_
        int _Sales_Stage_ID_
        int _Product_ID_
        decimal ProductRevenue
        datetime _Sales_Date_
        datetime _Closed_Date_
        int _Account_ID_
        int _Partner_ID_
    }
    SalesStages {
        double Probability
        string _Sales_Stage_
        int _Sales_Stage_ID_
    }
    Sales }o--|| Opportunities : "_Opportunity_ID_"
    Sales }o--|| SalesStages : "_Sales_Stage_ID_"
    Sales }o--|| Products : "_Product_ID_"
    Sales }o--|| Accounts : "_Account_ID_"
    Sales }o--|| Partners : "_Partner_ID_"
    Sales }o--|| Dates : "_Sales_Date_"
```

### `--measure` — DAX Measures

Generated from `pbi_sample_project` (Revenue Opportunities):

```
Sales.'Average Revenue'
AVERAGE([ProductRevenue])

Sales.'Total Opportunity Count'
COUNTA([Opportunity ID])

Sales.'Total Revenue'
SUM([ProductRevenue])

Sales.'Average Opportunity Days'
AVERAGEX(
    Sales,
    DATEDIFF(Sales[Sales Date], Sales[Closed Date], DAY)
)
```



