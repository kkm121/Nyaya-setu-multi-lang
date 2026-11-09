# Realistic, valid sample inputs for every document (used by tests and manual checks)
from datetime import timedelta

from nyaya.forms import today

T = today()


def d(days_ago):
    return (T - timedelta(days=days_ago)).isoformat()


ME = {"s_name": "Ravi Kumar", "s_rel": "S/o", "s_relname": "Mohan Kumar", "s_age": "34",
      "s_address": "12, Gandhi Street, Adyar, Chennai 600020", "s_phone": "+91 98765 43210",
      "s_email": "ravi.kumar@example.com", "place": "Chennai"}
THEM = {"r_name": "Suresh Babu", "r_rel": "S/o", "r_relname": "Krishnan", "r_address": "45, Anna Nagar 2nd Street, Madurai 625020"}

SAMPLES = {
    "police_complaint": dict(ME, station="Adyar", district="Chennai", offence="theft", incident_date=d(3),
                             incident_time="18:30", incident_place="Adyar bus stand, Chennai",
                             accused="Two unknown men on a black motorcycle", witnesses="Mr. Arun, a shop owner nearby",
                             facts="My mobile phone was snatched from my hand by two men on a motorcycle. They drove "
                                   "away towards the main road. The phone is a Samsung Galaxy worth about 25000 rupees. "
                                   "I shouted for help but they escaped.",
                             evidence=["screenshots", "bills"]),
    "reply_notice": dict(ME, n_from="Adv. Prakash Rao", n_from_address="7, Court Road, Egmore, Chennai 600008",
                         n_client="Sunrise Gadgets Pvt Ltd", n_date=d(10), n_received=d(7), n_ref="PR/2026/114",
                         facts="I posted a YouTube review of a product made by your client. The review was my honest "
                               "opinion based on my own use of the product. I have not made any false statement. Your "
                               "notice demands that I remove the video, which I refuse to do.",
                         reliefs=["withdraw", "no_proceedings"], other_relief="", days="15"),
    "cheque_notice": dict(ME, **THEM, cheque_no="004512", cheque_date=d(40), bank="State Bank of India, Madurai Main",
                          amount="150000", presented_date=d(15), return_date=d(12), reason="insufficient", basis="loan",
                          facts="I lent you 150000 rupees in March for your business. You promised to repay it within "
                                "three months. You then gave me a cheque for the full amount."),
    "consumer_complaint": dict(ME, op_name="QuickMart Electronics", op_address="22, Mount Road, Chennai 600002",
                               district="Chennai", state="Tamil Nadu", purchase_date=d(60),
                               product="LG refrigerator model GL-T292", amount="32500", bill_no="QM/8841",
                               facts="The refrigerator stopped cooling within ten days of delivery. I complained to the "
                                     "showroom and the company service centre several times. A technician visited but "
                                     "did not fix it. The warranty card says one year of free service.",
                               prior="Called the showroom five times and sent two emails",
                               reliefs=["refund", "compensation", "costs"], comp_amount="20000", cost_amount="5000"),
    "rti_application": dict(ME, level="state", authority="Office of the Commissioner, Greater Chennai Corporation",
                            authority_address="Ripon Building, Park Town, Chennai 600003",
                            subject="Repair of the road on Gandhi Street, Adyar",
                            period="01/04/2025 to 31/03/2026",
                            questions="Copy of the work order issued for repairing Gandhi Street road.\n"
                                      "Total amount sanctioned and spent on this work.\n"
                                      "Name of the contractor and the expected completion date.",
                            mode="post", fee="ipo", fee_ref="38F 123456"),
    "deposit_notice": dict(ME, **THEM, property="Flat 3B, Lake View Apartments, Velachery, Chennai 600042",
                           tenancy_start=d(800), vacated_on=d(45), amount="60000", deduction="5000",
                           facts="I gave you advance notice of one month before leaving. The flat was handed over in "
                                 "good condition, and you checked it in my presence. You have not replied to my calls.",
                           days="15", interest="9"),
}
