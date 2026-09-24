# Fixed 10-Row CUAD Classification/Retrieval Baseline

Status: **COMPLETE**

This is a read-only baseline of the current pipeline. It does not modify production code, segmentation, embeddings, Qdrant, Ollama, prompts, or risk analysis.

## Selection

- Fixed seed: `20260910`
- Source: `data/splits/test/master_clauses_test.csv`
- Source rows: `2556`; eligible rows: `1679`
- Metadata categories excluded: `Document Name`, `Parties`, `Agreement Date`, `Effective Date`, `Expiration Date`
- Future runs must reuse `selected_10_rows.json`; this runner does not resample when that file exists.

### Exact Selected Rows

| Rank | Stable ID | Original Row | Document ID | Ground Truth | Clause Text |
|---:|---|---:|---|---|---|
| 1 | `fixed-10-01` | 1906 | `LiquidmetalTechnologiesInc_20200205_8-K_EX-10.1_11968198_EX-10.1_Development Agreement.pdf` | `Warranty Duration` | Unless Liquidmetal notifies Eutectix that the Liquidmetal Product does not meet the Specifications within thirty (30) calendar days after receipt of the Liquidmetal Product, then the Liquidmetal Product shall be deemed Accepted. |
| 2 | `fixed-10-02` | 669 | `ENTERPRISEPRODUCTSPARTNERSLP_07_08_1998-EX-10.3-TRANSPORTATION CONTRACT.PDF` | `Price Restrictions` | When for Shipper's convenience a trailer is set out at the facilities of the    Consignor or Consignee or any other site designated, a charge of $10.00 per    hour or fraction thereof will apply, subject to a maximum charge of $100.00    per trailer in any consecutive twenty-four (24) hour period. |
| 3 | `fixed-10-03` | 1086 | `HYPERIONSOFTWARECORP_09_28_1994-EX-10.47-EXCLUSIVE DISTRIBUTOR AGREEMENT.PDF` | `Non-Compete` | During the term of this Agreement and for a period of two (2) years after the termination hereof for any reason, Distributor will not market, or attempt to market, a computer program which competes in any way with the Products in the areas of consolidation, financial information, financial transaction processing, reporting, data collection, or modeling, including but not limited to the use of personal computers, nor which competes with any modification, alteration or enhancement to the Products which is developed during the term of this Agreement. |
| 4 | `fixed-10-04` | 147 | `ANIXABIOSCIENCESINC_06_09_2020-EX-10.1-COLLABORATION AGREEMENT.PDF` | `Rofr/Rofo/Rofn` | If Anixa decides to not license those uses or compounds for this novel antiviral use, OntoChem is free to develop those molecules further as its own intellectual property without any further restrictions. |
| 5 | `fixed-10-05` | 432 | `RandWorldwideInc_20010402_8-KA_EX-10.2_2102464_EX-10.2_Co-Branding Agreement.pdf` | `Competitive Restriction Exception` | During the Term of this Agreement, PlanetCAD shall be permitted to market new functions and services relating to the Co-Branded Service directly to Dassault Systemes Customers with Dassault Systemes prior written approval, but only to the extent such functions and services are offered by PlanetCAD on the PlanetCAD Web site(s). |
| 6 | `fixed-10-06` | 1883 | `LiquidmetalTechnologiesInc_20200205_8-K_EX-10.1_11968198_EX-10.1_Development Agreement.pdf` | `Joint Ip Ownership` | To the extent that the Parties have jointly developed any New Amorphous Alloy Technology and they have agreed that such New Amorphous Alloy Technology will be jointly owned, as set forth in Section 8.2 above, each Party hereby assigns to the other, and will cause its employees, contractors, representatives, successors, assigns, Affiliates, parents, subsidiaries, officers and directors to assign to the other, a co-equal right, title and interest in and to any such jointly developed New Amorphous Alloy Technology. |
| 7 | `fixed-10-07` | 2096 | `CYBERIANOUTPOSTINC_07_09_1998-EX-10.13-PROMOTION AGREEMENT.PDF` | `Revenue/Profit Sharing` | For each month during the Term, the Company will pay CNET a                  minimum of [XXXX] in cash, plus [XXX] of CNET Sales. |
| 8 | `fixed-10-08` | 1238 | `THERAVANCEBIOPHARMA,INC_05_08_2020-EX-10.2-SERVICE AGREEMENT.PDF` | `Termination For Convenience` | The Company may, in its sole and absolute discretion, terminate the Executive's employment under this Agreement at any time and with immediate effect by notifying the Executive that the Company is exercising its right under this clause 17 and that it will make a payment in l ieu of  not ice ("PILON") to the Executive. |
| 9 | `fixed-10-09` | 2157 | `PHREESIA,INC_05_28_2019-EX-10.18-STRATEGIC ALLIANCE AGREEMENT.PDF` | `Audit Rights` | Each Party will bear all costs and expenses it incurs in connection with preparing for, conducting, or complying with any such audit including, in the case of the auditing Party, the costs and expenses of conducting the audit. |
| 10 | `fixed-10-10` | 2246 | `ArmstrongFlooringInc_20190107_8-K_EX-10.2_11471795_EX-10.2_Intellectual Property Agreement.pdf` | `Affiliate License-Licensor` | "Arizona Licensed Patents" means the Patents set forth on Schedule 1.1(l) and all other Patents owned by Licensing or Seller or their respective Affiliates as of the Effective Date and used or held for use in the Company Field during the five (5) years prior to the Effective Date (other than the Arizona Assigned Patents).<omitted>Subject to the terms and conditions of this Agreement, Arizona hereby grants to the Company a perpetual, non-exclusive, royalty-free license in, to and under the Arizona Licensed Patents for use in the Company Field throughout the world. |

## Environment

- Python: `3.12.14`
- Cohere query embedding model: `embed-english-v3.0`
- Embedding dimension: `1024`
- Qdrant collection: `cuad_train`
- Qdrant distance: `Cosine`
- Qdrant path: `/workspace/diagnostics/zto_retrieval_test/qdrant_snapshot` (isolated read-only snapshot)
- Retrieval Top-K: `5`
- Ollama endpoint: `http://host.docker.internal:11434`
- Ollama model: `llama3.2:3b`
- Runtime packages: `{"torch": "2.14.0+cpu", "qdrant-client": "1.19.0", "cohere": "7.1.1"}`

## Aggregate Metrics

- Recall@1: **0.5000**
- Recall@3: **0.6000**
- Recall@5: **0.6000**
- MRR: **0.5500**
- Final classification accuracy: **0.4000** (4/10)
- Ground truth in Top-5 but Ollama selected another category: **2**
- Ollama selected a category absent from Top-5: **1**

## Error Breakdown

- Retrieval miss (ground truth absent from Top-5): **4**
- Classification error (ground truth in Top-5, Ollama prediction differs): **2**
- Other/unsupported behavior (prediction absent from Top-5): **1**
- Pipeline errors: **0**

## Per-Row Results

| Row | Ground Truth | Qdrant Top-1 | Ollama Prediction | GT Rank | GT in Top-5 | Relationship |
|---|---|---|---|---:|---|---|
| `fixed-10-01` | `Warranty Duration` | `Warranty Duration` | `Warranty Duration` | 1 | Yes | `CORRECT` |
| `fixed-10-02` | `Price Restrictions` | `Revenue/Profit Sharing` | `Volume Restriction` | - | No | `RETRIEVAL_MISS` |
| `fixed-10-03` | `Non-Compete` | `Non-Compete` | `Non-Compete` | 1 | Yes | `CORRECT` |
| `fixed-10-04` | `Rofr/Rofo/Rofn` | `Non-Transferable License` | `Non-Transferable License` | - | No | `RETRIEVAL_MISS` |
| `fixed-10-05` | `Competitive Restriction Exception` | `Ip Ownership Assignment` | `License Grant` | - | No | `RETRIEVAL_MISS` |
| `fixed-10-06` | `Joint Ip Ownership` | `Ip Ownership Assignment` | `Ip Ownership Assignment` | 2 | Yes | `CLASSIFICATION_ERROR` |
| `fixed-10-07` | `Revenue/Profit Sharing` | `Revenue/Profit Sharing` | `License Grant` | 1 | Yes | `CLASSIFICATION_ERROR` |
| `fixed-10-08` | `Termination For Convenience` | `Termination For Convenience` | `Termination For Convenience` | 1 | Yes | `CORRECT` |
| `fixed-10-09` | `Audit Rights` | `Audit Rights` | `Audit Rights` | 1 | Yes | `CORRECT` |
| `fixed-10-10` | `Affiliate License-Licensor` | `Irrevocable Or Perpetual License` | `License Grant` | - | No | `RETRIEVAL_MISS` |

### fixed-10-01 — Warranty Duration

Clause: Unless Liquidmetal notifies Eutectix that the Liquidmetal Product does not meet the Specifications within thirty (30) calendar days after receipt of the Liquidmetal Product, then the Liquidmetal Product shall be deemed Accepted.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.530836 | `None` | `Warranty Duration` | If during the acceptance period described in Section 6, the Software has failed to perform in accordance with the Specifications and Garman has been unable to correct the deficiency within 45 business days of written notice being provided ... |
| 2 | 0.528245 | `None` | `Warranty Duration` | FCC shall promptly, but in no event later than three (3) days after the date of such purchase order, confirm its acceptance or rejection of such purchase order by written notice to Flotek. |
| 3 | 0.514186 | `None` | `Warranty Duration` | Any rejection or revocation of acceptance by Buyer (a) must be made within thirty (30) days of the products being made available for shipment to Buyer, (b) any attempted rejection or revocation of acceptance made thereafter shall be null a... |
| 4 | 0.514101 | `None` | `Warranty Duration` | If IBM has not notified MSL of any defects in a unit of Product within [*] Days of receipt, such unit shall<omitted>be deemed to be accepted. |
| 5 | 0.508124 | `None` | `Warranty Duration` | In the event that Magenta does not inform Bachem within the [***] period that the Product does not meet the Specifications, Magenta shall be deemed to have accepted the Product. |

Ollama raw response: `{"clause_type": "Warranty Duration"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-02 — Price Restrictions

Clause: When for Shipper's convenience a trailer is set out at the facilities of the    Consignor or Consignee or any other site designated, a charge of $10.00 per    hour or fraction thereof will apply, subject to a maximum charge of $100.00    per trailer in any consecutive twenty-four (24) hour period.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.469577 | `None` | `Revenue/Profit Sharing` | The Principal shall pay the Company a fee of $1.00 (one dollar), inclusive of VAT, per one net tonne of Commodity shipped pursuant to this Contract. |
| 2 | 0.469453 | `None` | `Notice Period To Terminate Renewal` | Thereafter, this Agreement shall be effective month to month, until terminated by Transporter or Shipper upon the following written notice to the other specifying a termination date: sixty (60) days for interruptible transportation under R... |
| 3 | 0.469453 | `None` | `Renewal Term` | Thereafter, this Agreement shall be effective month to month, until terminated by Transporter or Shipper upon the following written notice to the other specifying a termination date: sixty (60) days for interruptible transportation under R... |
| 4 | 0.448818 | `None` | `Minimum Commitment` | Sender with Contracted Capacity in Firm: 22.2.1 If by any reason the delivery is less than 95% or more than 105% of their Scheduled Capacity, the Sender shall Pay: 22.2.1.1.1 The Transportation fee for volumes delivered when they are highe... |
| 5 | 0.441971 | `None` | `Volume Restriction` | In addition to any other responsibilities stated in this Agreement, Company will: (a) Provide, at Distributor's reasonable request and without charge, up to 10 hours of training with regard to any characteristics of the Products that Distr... |

Ollama raw response: `{"clause_type": "Volume Restriction"}`
Ollama selected Top-1: **False**
Ollama selected another Top-K category: **True**
Ollama selected category absent from Top-K: **False**

### fixed-10-03 — Non-Compete

Clause: During the term of this Agreement and for a period of two (2) years after the termination hereof for any reason, Distributor will not market, or attempt to market, a computer program which competes in any way with the Products in the areas of consolidation, financial information, financial transaction processing, reporting, data collection, or modeling, including but not limited to the use of personal computers, nor which competes with any modification, alteration or enhancement to the Products which is developed during the term of this Agreement.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.633410 | `None` | `Non-Compete` | During the Term, of this Agreement and for an additional period of two (2) years from the date of termination of this Agreement, the Contractor undertakes not to develop on its own account any Product. |
| 2 | 0.585149 | `None` | `Non-Compete` | In the event that Distributor terminates this Agreement, then for one year thereafter, Distributor shall not sell, promote, advertise or market in the Territory products which are competitive with the Products. |
| 3 | 0.569864 | `None` | `Covenant Not To Sue` | During the Term of this Agreement and for three years thereafter, the Distributor (on behalf of itself and each of its affiliates) agrees not to commence, or provide any information to or otherwise assist any person or entity in connection... |
| 4 | 0.569448 | `None` | `No-Solicit Of Customers` | Distributor further agrees that it will not interfere with or otherwise disrupt the business relations between the Company or nay of its affiliates and any of their current or prospective customers, suppliers or distributors, during the<om... |
| 5 | 0.555265 | `None` | `Non-Compete` | Unless accepted by the Principal, the Distributor agrees that during the term of this Agreement, the Distributor, either directly or indirectly, shall handle no products that are competitive with the Products within the Territory. |

Ollama raw response: `{"clause_type": "Non-Compete"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-04 — Rofr/Rofo/Rofn

Clause: If Anixa decides to not license those uses or compounds for this novel antiviral use, OntoChem is free to develop those molecules further as its own intellectual property without any further restrictions.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.505184 | `None` | `Non-Transferable License` | Such usage may not be sold or transferred. |
| 2 | 0.505086 | `None` | `Non-Transferable License` | Such usage may not be sold or transferred. |
| 3 | 0.504936 | `None` | `Non-Transferable License` | Such usage may not be sold or transferred. |
| 4 | 0.476126 | `None` | `License Grant` | In the event that CAPSUGEL reasonably determines that the development of the Compound Formulation is not feasible with Commercially Reasonable Efforts in accordance with the Development Plan, with such changes as reasonably requested by CA... |
| 5 | 0.470096 | `None` | `License Grant` | During the Term, and without limiting Section 4.2, Achaogen hereby grants to Microgenics a royalty-free, exclusive, worldwide license to use the Achaogen<omitted>Know-How, Achaogen Patents, and Achaogen Materials to research, develop, manu... |

Ollama raw response: `{"clause_type": "Non-Transferable License"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-05 — Competitive Restriction Exception

Clause: During the Term of this Agreement, PlanetCAD shall be permitted to market new functions and services relating to the Co-Branded Service directly to Dassault Systemes Customers with Dassault Systemes prior written approval, but only to the extent such functions and services are offered by PlanetCAD on the PlanetCAD Web site(s).

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.511572 | `None` | `Ip Ownership Assignment` | In particular, Company agrees that, notwithstanding anything to the contrary set forth herein: (i) as part of Contractor's provision of the Services hereunder, Contractor may utilize its own proprietary works of authorship, that have not b... |
| 2 | 0.506411 | `None` | `License Grant` | The NFLA agrees to license such rights to the Company. |
| 3 | 0.492070 | `None` | `Affiliate License-Licensor` | Customer hereby grants to Manufacturer a non-exclusive license during the Term to use any Customer Property and Customer-Owned Improvements and Developments solely in connection with Manufacturer performing its obligations under this Agree... |
| 4 | 0.486942 | `None` | `License Grant` | Customer hereby grants to Manufacturer a non-exclusive license during the Term to use any Customer Property and Customer-Owned Improvements and Developments solely in connection with Manufacturer performing its obligations under this Agree... |
| 5 | 0.484350 | `None` | `Exclusivity` | Bosch hereby grants to Client the exclusive rights to sell and distribute the Product, subject to the Territory as set forth below, to certain select companies in the Automotive Industry, each of which shall be approved by Bosch in writing... |

Ollama raw response: `{"clause_type": "License Grant"}`
Ollama selected Top-1: **False**
Ollama selected another Top-K category: **True**
Ollama selected category absent from Top-K: **False**

### fixed-10-06 — Joint Ip Ownership

Clause: To the extent that the Parties have jointly developed any New Amorphous Alloy Technology and they have agreed that such New Amorphous Alloy Technology will be jointly owned, as set forth in Section 8.2 above, each Party hereby assigns to the other, and will cause its employees, contractors, representatives, successors, assigns, Affiliates, parents, subsidiaries, officers and directors to assign to the other, a co-equal right, title and interest in and to any such jointly developed New Amorphous Alloy Technology.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.587926 | `None` | `Ip Ownership Assignment` | Except with regard to the foregoing joint Inventions or methods, each party hereby assigns to the other, by way of present and future assignment, all of the right, title and interest (including all Intellectual Property Rights therein) tha... |
| 2 | 0.587926 | `None` | `Joint Ip Ownership` | Except with regard to the foregoing joint Inventions or methods, each party hereby assigns to the other, by way of present and future assignment, all of the right, title and interest (including all Intellectual Property Rights therein) tha... |
| 3 | 0.585409 | `None` | `Ip Ownership Assignment` | Each Party to whom ownership is to vest in Joint IP by operation of law or by assignment by its employees or Agents agrees to assign and hereby assigns to the other Party an undivided one-half right, title and interest in and to all Joint ... |
| 4 | 0.585409 | `None` | `Joint Ip Ownership` | Each Party to whom ownership is to vest in Joint IP by operation of law or by assignment by its employees or Agents agrees to assign and hereby assigns to the other Party an undivided one-half right, title and interest in and to all Joint ... |
| 5 | 0.574050 | `None` | `Joint Ip Ownership` | Copyright Materials that are jointly created by the Parties shall be jointly owned. |

Ollama raw response: `{"clause_type": "Ip Ownership Assignment"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-07 — Revenue/Profit Sharing

Clause: For each month during the Term, the Company will pay CNET a                  minimum of [XXXX] in cash, plus [XXX] of CNET Sales.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.509450 | `None` | `Revenue/Profit Sharing` | For monthly Cash Sales above [$●]the Base Royalty paid to T&B by LEA shall be [●%] of the LEA's Cash Sales. |
| 2 | 0.503446 | `None` | `Revenue/Profit Sharing` | For monthly Cash Sales above [$●] and up to [$●] the Base Royalty paid to T&B by LEA shall be [●%] of the LEA's Cash Sales |
| 3 | 0.501004 | `None` | `Revenue/Profit Sharing` | For monthly Cash Sales above [$●] and up to [$●] , the Base Royalty paid to T&B by LEA shall be [●%]of the LEA's Cash Sales |
| 4 | 0.501004 | `None` | `Revenue/Profit Sharing` | For monthly Cash Sales above [$●] and up to [$●], the Base Royalty paid to T&B by LEA shall be [●%] of the LEA's Cash Sales |
| 5 | 0.469719 | `None` | `Minimum Commitment` | The "Special Pricing" is contingent on a minimum order size of [***] users. |

Ollama raw response: `{"clause_type": "License Grant"}`
Ollama selected Top-1: **False**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **True**

### fixed-10-08 — Termination For Convenience

Clause: The Company may, in its sole and absolute discretion, terminate the Executive's employment under this Agreement at any time and with immediate effect by notifying the Executive that the Company is exercising its right under this clause 17 and that it will make a payment in l ieu of  not ice ("PILON") to the Executive.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.653160 | `None` | `Termination For Convenience` | 15.2 The Company may in its sole and absolute discretion (whether or not any notice of termination has been given under sub clause 15.1) terminate this Agreement at any time and with immediate effect by giving notice in writing to the Exec... |
| 2 | 0.562221 | `None` | `No-Solicit Of Employees` | You agree that during the term of this Agreement, you will not, without our prior written consent, either directly or indirectly through any other person or entity:<omitted>17.1.3. Induce any person to leave his or her employment with us. |
| 3 | 0.556112 | `None` | `Termination For Convenience` | This Agreement may be terminated at any time while the Employee is living by written notice thereof by either the Employer or the Employee to the other; and, in any event, this Agreement will terminate upon termination of the Employee's em... |
| 4 | 0.549439 | `None` | `Termination For Convenience` | The Company reserves the right in its sole and absolute discretion to give written notice to<omitted>terminate your employment forthwith and to make a payment to you in lieu of salary and the benefits set out in paragraph 5 of this Agreeme... |
| 5 | 0.544435 | `None` | `Termination For Convenience` | This Agreement may be terminated by Company at any time upon written notice to FIIOC. |

Ollama raw response: `{"clause_type": "Termination For Convenience"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-09 — Audit Rights

Clause: Each Party will bear all costs and expenses it incurs in connection with preparing for, conducting, or complying with any such audit including, in the case of the auditing Party, the costs and expenses of conducting the audit.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.668368 | `None` | `Audit Rights` | The cost of the audit will be borne by the Joint Venture. |
| 2 | 0.656139 | `None` | `Audit Rights` | The auditing Party shall bear the full cost of such audit unless such audit reveals an underpayment by the audited Party that resulted from a discrepancy in the financial report provided by the audited Party for the audited period, which u... |
| 3 | 0.649333 | `None` | `Audit Rights` | The audit will be performed by an accounting firm acceptable to all the Participants. |
| 4 | 0.632950 | `None` | `Audit Rights` | Costs incurred by Ehave in connection with any audit or inspection conducted shall be borne by Ehave. |
| 5 | 0.627342 | `None` | `Audit Rights` | In the case of an audit initiated by the Management Committee and exercised by the F&ASC, the audited Party or Parties shall be permitted to recover the entire costs of the review or audit from the Parties in the proportions specified in S... |

Ollama raw response: `{"clause_type": "Audit Rights"}`
Ollama selected Top-1: **True**
Ollama selected another Top-K category: **False**
Ollama selected category absent from Top-K: **False**

### fixed-10-10 — Affiliate License-Licensor

Clause: "Arizona Licensed Patents" means the Patents set forth on Schedule 1.1(l) and all other Patents owned by Licensing or Seller or their respective Affiliates as of the Effective Date and used or held for use in the Company Field during the five (5) years prior to the Effective Date (other than the Arizona Assigned Patents).<omitted>Subject to the terms and conditions of this Agreement, Arizona hereby grants to the Company a perpetual, non-exclusive, royalty-free license in, to and under the Arizona Licensed Patents for use in the Company Field throughout the world.

Top-5 retrieved results:

| Rank | Score | Document ID | Category | Clause Text |
|---:|---:|---|---|---|
| 1 | 0.753192 | `None` | `Irrevocable Or Perpetual License` | Subject to the terms and conditions of this Agreement, Arizona hereby grants to the Company a perpetual, non-exclusive, royalty-free license in, to and under the Arizona Licensed Patents for use in the Company Field throughout the world. |
| 2 | 0.753192 | `None` | `License Grant` | Subject to the terms and conditions of this Agreement, Arizona hereby grants to the Company a perpetual, non-exclusive, royalty-free license in, to and under the Arizona Licensed Patents for use in the Company Field throughout the world. |
| 3 | 0.724759 | `None` | `License Grant` | Subject to the terms and conditions of this Agreement, the Company hereby grants to Seller a perpetual, non-exclusive, royalty-free license in, to and under the Company Licensed Patents for use in the Arizona Field throughout the world. |
| 4 | 0.724759 | `None` | `Irrevocable Or Perpetual License` | Subject to the terms and conditions of this Agreement, the Company hereby grants to Seller a perpetual, non-exclusive, royalty-free license in, to and under the Company Licensed Patents for use in the Arizona Field throughout the world. |
| 5 | 0.712084 | `None` | `License Grant` | Subject to the terms and conditions of this Agreement, Arizona hereby grants to the Company a perpetual, non- exclusive, royalty-free license in, to and under the Arizona Licensed Know-How for use in the Company Field throughout the world. |

Ollama raw response: `{"clause_type": "License Grant"}`
Ollama selected Top-1: **False**
Ollama selected another Top-K category: **True**
Ollama selected category absent from Top-K: **False**

## Decision

This artifact is the fixed reference baseline for future retrieval/classification experiments. The benchmark exposes retrieval misses separately from Ollama classification changes. No system change is recommended from this baseline alone.

## Safety Check

- Only files under `diagnostics/fixed_10_classification_baseline/` were created or modified by this benchmark.
- The source test CSV was read but not modified.
- The Qdrant train collection was queried through an isolated read-only snapshot; no points or collections were written.
- No production source, segmentation code, embedding artifact, `.env`, Ollama model/configuration, prompt, or risk-analysis logic was changed.
- No Git commit was created.
