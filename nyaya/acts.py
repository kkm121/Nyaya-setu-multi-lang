# Act Names and Groups
# Names come from each act's own "short title" section in the corpus.

# code: (full name, short label, group)
ACTS = {
    # New criminal laws (in force from 1 July 2024)
    "BNS": ("Bharatiya Nyaya Sanhita, 2023", "BNS", "criminal"),
    "BNSS": ("Bharatiya Nagarik Suraksha Sanhita, 2023", "BNSS", "criminal"),
    "BSA": ("Bharatiya Sakshya Adhiniyam, 2023", "BSA", "criminal"),
    # Old criminal laws (still apply to offences before 1 July 2024)
    "IPC": ("Indian Penal Code, 1860", "IPC", "criminal_old"),
    "CRPC": ("Code of Criminal Procedure, 1973", "CrPC", "criminal_old"),
    "IEA": ("Indian Evidence Act, 1872", "Evidence Act", "criminal_old"),
    # Rights and constitution
    "COI": ("Constitution of India", "Constitution", "rights"),
    "RTI": ("Right to Information Act, 2005", "RTI Act", "rights"),
    "LSAA": ("Legal Services Authorities Act, 1987", "Legal Services Act", "rights"),
    "SCST": ("Scheduled Castes and the Scheduled Tribes (Prevention of Atrocities) Act, 1989", "SC/ST Act", "rights"),
    "PCRA": ("Protection of Civil Rights Act, 1955", "PCR Act", "rights"),
    "PHRA": ("Protection of Human Rights Act, 1993", "Human Rights Act", "rights"),
    "RPWDA": ("Rights of Persons with Disabilities Act, 2016", "RPwD Act", "rights"),
    "RTE": ("Right of Children to Free and Compulsory Education Act, 2009", "RTE Act", "rights"),
    "POSH": ("Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013", "POSH Act", "rights"),
    "POCSO": ("Protection of Children from Sexual Offences Act, 2012", "POCSO Act", "rights"),
    "JJ": ("Juvenile Justice (Care and Protection of Children) Act, 2015", "JJ Act", "rights"),
    "MHA": ("Mental Healthcare Act, 2017", "Mental Healthcare Act", "rights"),
    # Money, consumer and everyday disputes
    "NIA": ("Negotiable Instruments Act, 1881", "NI Act", "money"),
    "CPA": ("Consumer Protection Act, 2019", "Consumer Protection Act", "money"),
    "ICA": ("Indian Contract Act, 1872", "Contract Act", "money"),
    "SGA": ("Sale of Goods Act, 1930", "Sale of Goods Act", "money"),
    "SRA": ("Specific Relief Act, 1963", "Specific Relief Act", "money"),
    "LA": ("Limitation Act, 1963", "Limitation Act", "money"),
    "CPC": ("Code of Civil Procedure, 1908", "CPC", "money"),
    "IT_ACT": ("Information Technology Act, 2000", "IT Act", "cyber"),
    "DPDPA": ("Digital Personal Data Protection Act, 2023", "DPDP Act", "cyber"),
    "TELECOM": ("Telecommunications Act, 2023", "Telecom Act", "cyber"),
    "MVA": ("Motor Vehicles Act, 1988", "Motor Vehicles Act", "traffic"),
    # Property and housing
    "TPA": ("Transfer of Property Act, 1882", "Transfer of Property Act", "property"),
    "REGISTRATION": ("Registration Act, 1908", "Registration Act", "property"),
    "STAMP": ("Indian Stamp Act, 1899", "Stamp Act", "property"),
    "RERA": ("Real Estate (Regulation and Development) Act, 2016", "RERA", "property"),
    "EASEMENTS": ("Indian Easements Act, 1882", "Easements Act", "property"),
    "RFCTLARR": ("Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013", "Land Acquisition Act", "property"),
    # Family
    "HMA": ("Hindu Marriage Act, 1955", "Hindu Marriage Act", "family"),
    "HSA": ("Hindu Succession Act, 1956", "Hindu Succession Act", "family"),
    "HAMA": ("Hindu Adoptions and Maintenance Act, 1956", "HAMA", "family"),
    "SMA": ("Special Marriage Act, 1954", "Special Marriage Act", "family"),
    "ISA": ("Indian Succession Act, 1925", "Succession Act", "family"),
    "GWA": ("Guardians and Wards Act, 1890", "Guardians and Wards Act", "family"),
    "DV": ("Protection of Women from Domestic Violence Act, 2005", "DV Act", "family"),
    "DPA": ("Dowry Prohibition Act, 1961", "Dowry Prohibition Act", "family"),
    "PCMA": ("Prohibition of Child Marriage Act, 2006", "Child Marriage Act", "family"),
    "FCA": ("Family Courts Act, 1984", "Family Courts Act", "family"),
    "MWPSC": ("Maintenance and Welfare of Parents and Senior Citizens Act, 2007", "Senior Citizens Act", "family"),
    "MWPRDA": ("Muslim Women (Protection of Rights on Divorce) Act, 1986", "Muslim Women (Divorce) Act", "family"),
    "MWPRMA": ("Muslim Women (Protection of Rights on Marriage) Act, 2019", "Muslim Women (Marriage) Act", "family"),
    # Work
    "COW": ("Code on Wages, 2019", "Code on Wages", "work"),
    "CSS": ("Code on Social Security, 2020", "Social Security Code", "work"),
    "IRC": ("Industrial Relations Code, 2020", "Industrial Relations Code", "work"),
    "OSH": ("Occupational Safety, Health and Working Conditions Code, 2020", "OSH Code", "work"),
    "CALPRA": ("Child and Adolescent Labour (Prohibition and Regulation) Act, 1986", "Child Labour Act", "work"),
    # Other special laws
    "NDPS": ("Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS Act", "special"),
    "ARMS": ("Arms Act, 1959", "Arms Act", "special"),
    "PCA": ("Prevention of Corruption Act, 1988", "Prevention of Corruption Act", "special"),
    "PMLA": ("Prevention of Money-laundering Act, 2002", "PMLA", "special"),
    "UAPA": ("Unlawful Activities (Prevention) Act, 1967", "UAPA", "special"),
    "ADVOCATES": ("Advocates Act, 1961", "Advocates Act", "special"),
    "CONTEMPT_COURTS": ("Contempt of Courts Act, 1971", "Contempt of Courts Act", "special"),
    "COMMERCIAL_COURTS": ("Commercial Courts Act, 2015", "Commercial Courts Act", "special"),
    "ATA": ("Administrative Tribunals Act, 1985", "Administrative Tribunals Act", "special"),
    "RPA": ("Representation of the People Act, 1951", "RP Act", "special"),
    "FSSA": ("Food Safety and Standards Act, 2006", "Food Safety Act", "special"),
    "DCA": ("Drugs and Cosmetics Act, 1940", "Drugs and Cosmetics Act", "special"),
    "EA": ("Electricity Act, 2003", "Electricity Act", "special"),
    "AADHAAR": ("Aadhaar (Targeted Delivery of Financial and Other Subsidies, Benefits and Services) Act, 2016", "Aadhaar Act", "special"),
    # Environment
    "EPA": ("Environment (Protection) Act, 1986", "Environment Act", "environment"),
    "AIR": ("Air (Prevention and Control of Pollution) Act, 1981", "Air Act", "environment"),
    "WATER": ("Water (Prevention and Control of Pollution) Act, 1974", "Water Act", "environment"),
    "WPA": ("Wild Life (Protection) Act, 1972", "Wildlife Act", "environment"),
    "NGT": ("National Green Tribunal Act, 2010", "NGT Act", "environment"),
    "VSA": ("Van (Sanrakshan Evam Samvardhan) Adhiniyam, 1980", "Forest Act", "environment"),
    # Business, tax and finance
    "CA": ("Companies Act, 2013", "Companies Act", "business"),
    "LLP": ("Limited Liability Partnership Act, 2008", "LLP Act", "business"),
    "IPA": ("Indian Partnership Act, 1932", "Partnership Act", "business"),
    "IBC": ("Insolvency and Bankruptcy Code, 2016", "IBC", "business"),
    "ACA": ("Arbitration and Conciliation Act, 1996", "Arbitration Act", "business"),
    "COMPETITION": ("Competition Act, 2002", "Competition Act", "business"),
    "MSMED": ("Micro, Small and Medium Enterprises Development Act, 2006", "MSMED Act", "business"),
    "CHIT": ("Chit Funds Act, 1982", "Chit Funds Act", "business"),
    "ITA": ("Income-tax Act, 2025", "Income-tax Act", "business"),
    "CGST": ("Central Goods and Services Tax Act, 2017", "CGST Act", "business"),
    "IGST": ("Integrated Goods and Services Tax Act, 2017", "IGST Act", "business"),
    "CUSTOMS": ("Customs Act, 1962", "Customs Act", "business"),
    "FEMA": ("Foreign Exchange Management Act, 1999", "FEMA", "business"),
    "FCRA": ("Foreign Contribution (Regulation) Act, 2010", "FCRA", "business"),
    "BRA": ("Banking Regulation Act, 1949", "Banking Regulation Act", "business"),
    "RBI": ("Reserve Bank of India Act, 1934", "RBI Act", "business"),
    "PSSA": ("Payment and Settlement Systems Act, 2007", "Payment Systems Act", "business"),
    "SARFAESI": ("Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002", "SARFAESI Act", "business"),
    "RDBA": ("Recovery of Debts and Bankruptcy Act, 1993", "Recovery of Debts Act", "business"),
    "INSURANCE": ("Insurance Act, 1938", "Insurance Act", "business"),
    "IRDAI": ("Insurance Regulatory and Development Authority Act, 1999", "IRDAI Act", "business"),
    "SEBI": ("Securities and Exchange Board of India Act, 1992", "SEBI Act", "business"),
    "SCRA": ("Securities Contracts (Regulation) Act, 1956", "SCRA", "business"),
    "PBPTA": ("Prohibition of Benami Property Transactions Act, 1988", "Benami Act", "business"),
    "COPYRIGHT": ("Copyright Act, 1957", "Copyright Act", "business"),
    "PATENTS": ("Patents Act, 1970", "Patents Act", "business"),
    "TRADEMARKS": ("Trade Marks Act, 1999", "Trade Marks Act", "business"),
    "DESIGNS": ("Designs Act, 2000", "Designs Act", "business"),
    "GI": ("Geographical Indications of Goods (Registration and Protection) Act, 1999", "GI Act", "business"),
}

# Old law -> new law
OLD_TO_NEW = {"IPC": "BNS", "CRPC": "BNSS", "IEA": "BSA"}
NEW_TO_OLD = {v: k for k, v in OLD_TO_NEW.items()}

# Acts ordinary people need most (small ranking boost)
COMMON_ACTS = {"BNS", "BNSS", "BSA", "COI", "NIA", "CPA", "RTI", "TPA", "DV", "HMA",
               "MVA", "IT_ACT", "LSAA", "MWPSC", "DPA", "ICA", "LA", "SCST", "POSH", "COW"}

# Date the new criminal laws started
NEW_LAW_START = "2024-07-01"


def act_name(code):
    return ACTS.get(code, (code, code, "other"))[0]


def act_label(code):
    return ACTS.get(code, (code, code, "other"))[1]


def act_group(code):
    return ACTS.get(code, (code, code, "other"))[2]
