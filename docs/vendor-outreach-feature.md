Build a feature vendor outreach agent on top of the parts procurement copilot.

The user flow now becomes 

user enteres vin + query, tag it as standard or urgent
parts are surfaced with fitments with vendors selling it
user clicks on part, clicks create request now rather than order
agent builds an outreach email
job is created
job will be logged to procurement board which will be new ui layer showing all current procurement boards
response will come in, response will be parsed, in the case of follow up required, itll show follow up required, follow up sent, 
if response has all emails, list as confirmed and send to rank in algorithm with fields, finally complete after accepted

job board will be updating live
                                                                                                                                                                            (unsuccessful)
state machine has following transitions: click on card (request product) --> Confirm out reach -- > outreach sent --> awaiting response --> response received --> parsed ----> follow up required --> follow up sent editable field --> if successful extraction and availability, go through success path
                                                                                                                                                                    |
                                                                                                                                                                    | successful (all fields available)
                                                                                                                                                                    |
                                                                                                                                                                    confirmed
                                                                                                                                                                    |
                                                                                                                                                                    |
                                                                                                                                                                    send for ranking
                                                                                                                                                                    |
                                                                                                                                                                    |
                                                                                                                                                                    |
                                                                                                                                                                    provide value of ranking, confirm request



step 1 is to use vendors.md and add it to parts table in supabase, augment it and match accordingly. multiple vendors can have same part, generate delivery dates in random formats here, its the LLM's job to understand from data, if urgent is now selected, list a time window as well in the frontend
user will select part from procurement and itll show vendors with eta, select one vendor, 
step 2 is generation, LLM would generate email, use lightweight model such as claude haiku for this

step 3 is generate emails based on vendors.md response rate, it can be random based on the part selected and the vendors who can source, vendor email responses should consist of 4 fields : availability statuys, unit price, quanity availabvle, estimated delivery date. create job which responds accordingly based on the response rate, higher response rate vendors will respond quicker, each format should have different voices, different formats, use claude haiku for this as well. It should also parse using claude haiku. emails can randomly be missing some of the required fields
step 4 : job board should update statuses live based on state machine state, 
step 5 : if all fields available and successful and in time window of user then, send for ranking. Ranking formula should consist of price at 0.4, delivery time at 0.4, vendor historial response rate at 0.2. 

views should include procurement board showing name, current stauts, time elapsed, last action taken
vendor info when clicked should show as side panel with response text, parsed fields, any follow up generated and approval status and composute score if ranking has been computed

eval counter which shows the parser accuracy is extracting fields, this is not on the ui, keep it separate