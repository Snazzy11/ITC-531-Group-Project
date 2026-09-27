# Profile
## APIs

| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | ~19,200                                                | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours | 2      |
| Duration                | 50-70+ ms ; 100-150 ms                                 | 3      |
| Memory                  | 100 mb                                                 | 4      |
| Concurrency             | Relatively high (for matching operations especially)   | 5      |
| State required          | State required; items need to be put into database     | 6      |
| Latency budget          | 1s                                                     | 7      |
| Long-running risk       | Low                                                    | 8      |
### Methods
1. As the app is being built for the campus, the userbase will consist of students and staff on campus who have lost or found items around campus. As of 2025, there were just over 14000 students$^1$ enrolled at CMU and just over 2000 staff members$^2$. Therefore, the total count of *potential* users we could scale for at CMU would be 16000 as of right now. In a given month, assuming 30% of these people (a rough guess) lost (or found) items, the API calls that would need to be made to match and return an item (in an ideal scenario) would be 4. Two to post the given item as a lost item and a found item (by two separate users), one to create the match and one to delete the match after reuniting the item with its owner. That would give us 19,200 (4800x4) requests. The actual number of reqeusts would almost certainly end up north of this estimation to account for items that may not ever be reunited, among other factors and edge-cases, but it provides a working estimate to start from.
	1. https://www.cmich.edu/offices-departments/academic-planning-and-analysis/reports/enrollment-reports
	2. https://www.univstats.com/staffs/central-michigan-university/faculty-status/
2. The arrival pattern for requests to the API will be dictated primarily by the event of an item being either lost or found by the user. That said, arrivals will likely be more frequent during school hours, when the most amount of users would be on campus and able to lose or find items.
3. Guess: 50+ ms p50; 100-150 ms p95
4. Estimate based on container using ```docker stats```.
5. Concurrency is to be expected. The operations with the most concurrency will likely be those related to matching, the posting of a new item will require that the existing items posted to the application be checked for potential matches and users will then need to be notified of these potential matches. Because of this, the posting of a singular item may require concurrent operations proportional to that of the items within the system.
6. State will be required in order to place new items within the database.
7. Beyond one-second slowdown may be noticeable.
8. The work done wihtin the API should not have significant risk for long-running operations.
## Gateway
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | >19,200                                                | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours | 2      |
| Duration                | 30+ ms ; 70+ ms                                        | 3      |
| Memory                  | 10 mb                                                  | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | No state required                                      | 6      |
| Latency budget          | 200 ms                                                 | 7      |
| Long-running risk       | Very low                                               | 8      |
### Methods
1. As all requests to the API will first be routed through the gateway, the potential monthly requests to the gateway will be lower-bounded by that of those to the API. 
2. Simiarily to the arrival pattern to the API, requests to the gateway will be event-driven by the loss (or finding) of an item, with school hours being particualrly busy.
3. Guess: 20+ ms p50, ; less than the API as the gateway just sits before the API.
4. Estimate based on container using ```docker stats```.
5. Concurrency to the gateway will also be relatively high as was the case for the API as all requests will be routed through the gateway first. 
6. No state will be required for the gateway; nothing the gateway achieves will need to be stored or saved.
7. The gateway should have a short duration and as such the latency budget should be relatively low too.
8. The gateway should not have any long-running operations.
## Image Worker
| Field                   | Estimate                                                            | Method |
| ----------------------- | ------------------------------------------------------------------- | ------ |
| Requests/jobs per month | ~4800                                                               | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours              | 2      |
| Duration                | Not (yet) applicable                                                | 3      |
| Memory                  | Not (yet) applicable                                                | 4      |
| Concurrency             | Relatively low                                                      | 5      |
| State required          | Yes; images will need to be stored in the database post-processing. | 6      |
| Latency budget          | Not (yet) applicable                                                | 7      |
| Long-running risk       | Potentially high                                                    | 8      |
### Methods
1. Working from the earlier estimate for the API requests, assuming 30% of of the potential maximum userbase locates items and posts them all with images, that would give around 4800 jobs for the image worker to process per month. 
2. As with the API, work for the image worker will be event-driven and likely peaking during school hours.
3. Not yet applicable, the functionality for the image worker is not implemented currently.
4. Not yet applicable, the functionality for the image worker is not implemented currently.
5. Concurrency for the image worker will be relatively low; any concurrency will be dictated by items being posted at the same time, far from impossible but likely not typical.
6. State will be required for the image worker; after images are processed they will need to be stored within the database. Currently the functionality for the image worker is not implemented.
7. Not yet applicable, the functionality for the image worker is not implemented currently.
8. Processing large images may lead to some risk for long invocations.
## Matching Worker
| Field                   | Estimate                                                                     | Method |
| ----------------------- | ---------------------------------------------------------------------------- | ------ |
| Requests/jobs per month | >4800                                                                        | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours                       | 2      |
| Duration                | Not (yet) applicable                                                         | 3      |
| Memory                  | Not (yet) applicable                                                         | 4      |
| Concurrency             | High                                                                         | 5      |
| State required          | State required; matches wll need to be stored and saved within the database. | 6      |
| Latency budget          | Not (yet) applicable                                                         | 7      |
| Long-running risk       | Not (yet) applicable                                                         | 8      |
### Methods
1.  Again working from the 30% estimate from earlier, if 4800 users have the need to locate an item, the matching worker will then have a baseline of 4800 matches to make. Additionally, the figure will likely be higher than this to account for false-flags and/or incorrect matches.
2. The work for the matching worker will be dictated by the event of items being posted, and once again the peak time will likely be during school hours.
3. Not yet applicable, functionality has not been implemented for the matching worker.
4. Not yet applicable, functionality has not been implemented for the matching worker.
5.  Concurrency for the matching worker may be rather high; new items being posted will require them to be compared to the existing items within the database to search for potential matches.
6. State will be required for the matching worker; when a potential match is found it will need to be stored within the database so a user will be able to determine whether or not the match is correct.
7. Not yet applicable, functionality has not been implemented for the matching worker.
8. Not yet applicable, functionality has not been implemented for the matching worker.
## Message Broker
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | >19,200                                                | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours | 2      |
| Duration                | 20-40 ms p50; 80+ ms p95                               | 3      |
| Memory                  | 200 mb                                                 | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | No state required                                      | 6      |
| Latency budget          | 200 ms                                                 | 7      |
| Long-running risk       | Minor                                                  | 8      |
### Methods
1.  The earlier estimate for the APIs jobs per month will be useful here too. Assuming the 4800 missing items figure, and knowing that each item will require at least 4 messages (to the matching queue, image processing queue, logger, and notifier) gives us a similar number to that of the API requests. Messaging will also involve additional jobs due to the additional logging/notifying involved in the processing of the matching and images. 
2. The arrival pattern for the message broker will be event-driven, driven both by the events of items being posted as well as processing for existing items within the application. School hours will affect the volume of requests here as well.
3. Guess: 20-40 ms p50 ; 80+ ms p95
4. Estimate based on container using ```docker stats```.
5.  Concurrency will be high for the message broker; items will be processed on a regular basis and messages will be sent throughout the application in order to account for this.
6. No state will be required for the message broker.
7. Guess: 200 ms 
8. The message broker should not have any tasks that will be risk of running for egrigious amounts of time.
## Notifier
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | ~4800                                                  | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours | 2      |
| Duration                | 20-40 ms p50; 80+ ms p95                               | 3      |
| Memory                  | 40 mb                                                  | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | No state required                                      | 6      |
| Latency budget          | 200 ms                                                 | 7      |
| Long-running risk       | Low                                                    | 8      |
### Methods
1.  Assuming the figure of 4800 items from above, the notifier will need to bring attention of any potential matches to the user's who have posted lost items.
2. The arrival patterns for the notifier will be event-driven by the matching of items; as with all of the other components, care will need to be given to the fact that school hours will likely lead to an influx of events.
3. 
4. Estimate based on container using ```docker stats```.
5. Concurrency will be high for the notifier, dictated primarily by the concurrency of matches being made by the matching worker. 
6. State wil not be required for the notifier.
7. Guess: 200 ms
8. The notifier should have little risk for any lon-running operations.
## Logger
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | >4800                                                  | 1      |
| Arrival Pattern         | Event-driven, likely more frequent during school hours | 2      |
| Duration                | 15-30 ms p50 ; 60+ ms p95                              | 3      |
| Memory                  | 40 mb                                                  | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | State required, logs will be stored within a log file. | 6      |
| Latency budget          | 100 ms                                                 | 7      |
| Long-running risk       | Very Low                                               | 8      |
### Methods
1.  The logger will have various events to log throughout the app; the 4800 figure provides a baseline but the actual number of jobs wille certainly be higher.
2. The logger will take care of the variosu events happening throughout the application and as such will be event-driven by nature (as the rest of the components will be). School hours will be peak hours.
3. Guess: 15-30 ms p50; 60+ ms p95
4. Estimate based on container using ```docker stats```.
5.  Concurrency will be high for the logger; events will be logged throughout the various components of the application and these events will be logged concurrently as they are happening.
6. State will be required for the logger, events will be logged within a file in case the need arises to read and analyze them.
7. Guess: 100 ms
8. The logger should not have any long-running operations.
# Measured Baseline
