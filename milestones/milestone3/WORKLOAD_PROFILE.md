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
1. As the app is being built for the campus, the userbase will consist of students and staff on campus who have lost or found items around campus. As of 2025, there were just over 14000 students enrolled at CMU and just over 2000 staff members. Therefore, the total count of *potential* users we could scale for at CMU would be 16000 as of right now. In a given month, assuming 30% of these people (a rough guess) lost (or found) items, the API calls that would need to be made to match and return an item (in an ideal scenario) would be 4. Two to post the given item as a lost item and a found item (by two separate users), one to create the match and one to delete the match after reuniting the item with its owner. That would give us 19,200 (4800x4) requests. The actual number of reqeusts would almost certainly end up north of this estimation to account for items that may not ever be reunited, among other factors and edge-cases, but it provides a working estimate to start from.
	1. https://www.cmich.edu/offices-departments/academic-planning-and-analysis/reports/enrollment-reports
	2. https://www.univstats.com/staffs/central-michigan-university/faculty-status/
2. The arrival pattern for requests to the API will be dictated primarily by the event of an item being either lost or found by the user. That said, arrivals will likely be more frequent during school hours, when the most amount of users would be on campus and able to lose or find items.
3. Guess: 50+ ms p50; 100-150 ms p95
4. Estimate based on container using ```docker stats``` on our machines.
5. Concurrency is to be expected. The operations with the most concurrency will likely be those related to matching, the posting of a new item will require that the existing items posted to the application be checked for potential matches and users will then need to be notified of these potential matches. Because of this, the posting of a singular item may require concurrent operations proportional to that of the items within the system.
6. State will be required in order to place new items within the database.
7. Beyond two-second slowdown would be noticeable. Think of scrolling down a list of items and their photos. Reaching the bottom and having to wait more than 2 seconds is annoying. However, the nature of having to stop and look at each item in your category gives us plenty of time to load new items. 
8. The work done wihtin the API should not have significant risk for long-running operations. The task of calculating matches is O(n) where n is the number of unmatched items in the database, for each item to be matched. However, this is an asynchronous background task and not returned by the API.
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
| Arrival Pattern         | Event-driven, likely more frequent just after school hours              | 2      |
| Duration                | Not (yet) applicable                                                | 3      |
| Memory                  | Not (yet) applicable                                                | 4      |
| Concurrency             | Relatively low                                                      | 5      |
| State required          | Yes; images will need to be stored in the database post-processing. | 6      |
| Latency budget          | Not (yet) applicable                                                | 7      |
| Long-running risk       | Potentially high                                                    | 8      |
### Methods
1. Working from the earlier estimate for the API requests, assuming 30% of of the potential maximum userbase locates items and posts them all with images, that would give around 4800 jobs for the image worker to process per month. 
2. As with the API, work for the image worker will be event-driven and likely peaking right at the end of school hours, where students get home and realize they forgot something.
3. Not yet applicable, the functionality for the image worker is not implemented currently, and it has not been requested that we write this code yet. Estimate is based on the resoution of the uploaded image, and on the single core performance of the CPU it is done on. This makes it very difficult to provide any good estimate, but under a minute for each image is almost certain, and in fact it would be a good idea to stop the task if it takes longer than this.
4. Not yet applicable, the functionality for the image worker is not implemented currently. No data to base an estiamate on.
5. Concurrency for the image worker will be relatively low; any concurrency will be dictated by items being posted at the same time, far from impossible but likely not typical. There is no problem with queing images back to back instead of trying to parallelize it.
6. State will be NOT required for the actual image worker. After images are processed they will need to be stored as files, with paths stored in the database. That will be given to the database where persistent data is held, but not held in the worker. Currently the functionality for the image worker is not implemented.
7. Latency is not a concern, since the result is not returned to the user, and the server just adds it to the message queue. Getting the job done quickly is also unimportant, since it is extremely unlikely that somebody tries to upload a match in a very short timespan after the first item was uploaded.
8. Processing large images may lead to some risk for long invocations. Once again, a blocking task isnt much of a problem since the image wont be needed immediately after uploading.
## Matching Worker
| Field                   | Estimate                                                                     | Method |
| ----------------------- | ---------------------------------------------------------------------------- | ------ |
| Requests/jobs per month | >4800                                                                        | 1      |
| Arrival Pattern         | Event-driven, with noticeable peak hours                       | 2      |
| Duration                | Not (yet) applicable                                                         | 3      |
| Memory                  | Not (yet) applicable                                                         | 4      |
| Concurrency             | High                                                                         | 5      |
| State required          | State required; matches wll need to be stored and saved within the database. | 6      |
| Latency budget          | Not (yet) applicable                                                         | 7      |
| Long-running risk       | Not (yet) applicable                                                         | 8      |
### Methods
Note: I would like to add some background to how this feature will work. A list of tags will be attached to the items and used in an attempt to produce a matching score. The words in the item descriptions will be used in that score as well. The items with the highest potential scores will be given to the user and they will determine the match. The specifics of this dont quite match our original specifications for the database, but this is how we plan it now.
1.  Again working from the 30% estimate from earlier, if 4800 users have the need to locate an item, the matching worker will then have a baseline of 4800 matches to make. Additionally, the figure will likely be higher than this to account for false-flags and/or incorrect matches.
2. The work for the matching worker will be dictated by the event of items being posted, and once again the peak time will likely be at the end of school hours.
3. Not yet applicable, the functionality for the matching worker is not implemented currently, and it has not been requested that we write this code yet. It is hard to produce an estimate, as the O(n) nature will grow as the app grows. Even a few thousand items should take seconds or less as very few fields need to be checked.
4. Not yet applicable or able to make a prediction, functionality has not been implemented for the matching worker. Memory should stay fairly low, as containers have proven to not take much space and the scan will only be a bit of ascii text data.
5. Concurrency for the matching worker may be rather high; new items being posted will require them to be compared to the existing items within the database to search for potential matches. Hopefully in the future we can decide a way to reduce scan time by optimizing the algorithm, using heuristics, and possibly trying to match multiple similar items at the same time by grouping them and running the search once.
6. State will NOT be required for the matching worker specifically; when a potential match is found it will just need to sent back to the database container to be stored within the database so a user will be able to determine whether or not the match is correct. The acutal matching working is only functional, but it needs to be attached to persistent data.
7. Not yet entirely applicable, since functionality has not been implemented for the matching worker. This job is asynchronous so a 202 response should be fast but the worker can take its time. Another worker is responsible for actually sending a notification to the user, and it can be done at any time.
8. Not yet entirely applicable, functionality has not been implemented for the matching worker. As the database grows, this will eventually become more and more likely to happen. It should be easy to scale up the CPU to give this a faster runtime, or to purge old data later on.
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
5.  Concurrency will be high for the message broker; it has many jobs and items will be processed on a regular basis.
6. No state will be required for the message broker. It does not need to store anything and only pass around data. It should not be brought up functionally though.
7. Guess: 300 ms. It has a lot of jobs and spikes in latency will happen. Almost everything it has to pass around is not time senstive, but an especially long latency time could cause many messages to back up quickly and cause a cascade to failure.
8. The message broker should not have any tasks that will be risk of running for egrigious amounts of time.
## Notifier
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | ~4800                                                  | 1      |
| Arrival Pattern         | Event-driven, likely more frequent after school hours | 2      |
| Duration                | A wide range, dependant on a lot of factors                               | 3      |
| Memory                  | 40 mb                                                  | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | No state required                                      | 6      |
| Latency budget          | Very high, almost inconsequential                                              | 7      |
| Long-running risk       | Low                                                    | 8      |
### Methods
1.  Assuming the figure of 4800 items from above, the notifier will need to bring attention of any potential matches to the user's who have posted lost items.
2. The arrival patterns for the notifier will be event-driven by the matching of items; as with all of the other components, care will need to be given to the fact that school hours will likely lead to an influx of events.
3. Hard to give an exact estimate but could range to be several minutes. We will be reliant on many slow external services, including SMTP, SMS through cell providers, likely another company with an API to handle this scenario rather than trying to work with SMS ourselves.
4. Estimate based on container using ```docker stats```.
5. Concurrency will be medium to high for the notifier, dictated primarily by the concurrency of matches being made by the matching worker, and secondarily by the delay in external services.
6. State wil not be required for the notifier, it should only respond and act on ephemeral data.
7. A notification should be sent when a match is found, but people are slow and there is no reason to pretend like this action is high priority. A delay of more than 30 minutes would be a problem, but this scenario would never be reached.
8. The notifier should have little risk for any lon-running operations, but could have long times of holding open connections using external APIs.
## Logger
| Field                   | Estimate                                               | Method |
| ----------------------- | ------------------------------------------------------ | ------ |
| Requests/jobs per month | >4800                                                  | 1      |
| Arrival Pattern         | Event-driven, likely more frequent after school hours | 2      |
| Duration                | 15-30 ms p50 ; 60+ ms p95                              | 3      |
| Memory                  | 40 mb                                                  | 4      |
| Concurrency             | High                                                   | 5      |
| State required          | State required, logs will be stored within a log file. | 6      |
| Latency budget          | 100 ms                                                 | 7      |
| Long-running risk       | Very Low                                               | 8      |
### Methods
1.  The logger will have various events to log throughout the app; the 4800 figure provides a baseline but the actual number of jobs will grow linearly with that number.
2. The logger will take care of the logging the various events happening throughout the application and as such will be event-driven by nature (as the rest of the components will be). After school hours will be peak hours.
3. Guess: 10-30 ms p50; 50+ ms p95. Dependant on storage latency.
4. Estimate based on container using ```docker stats```.
5.  Concurrency will be high for the logger; lots of events will be logged throughout the various components of the application and these events will be logged concurrently as they are happening.
6. State will be required for the logger, events will be logged within a file in case the need arises to read and analyze them.
7. Guess: 100 ms. Higher than this might cause an exponential backlog of tasks and freeze the app in a hard to diagnose way.
8. The logger should not have any long-running operations. 

# Measured Baseline
We created a python script to measure the exact latency on every request. For the warm latency, 10 requests were sent with nothing recorded, and then another 50 are measured. Then the measurements are inspected and counted to produce the numbers below.

```bash
# host/function warm latency
requests: 100
average_ms: 0.329
p95_ms: 0.441
raw_ms:
0.350,0.334,0.293,0.309,0.318,0.296,0.300,0.559,0.394,0.483,0.417,0.410,0.434,0.367,0.375,0.366,0.452,0.441,0.412,0.381,0.382,0.333,0.307,0.337,0.315,0.349,0.340,0.387,0.337,0.485,0.317,0.299,0.313,0.307,0.384,0.351,0.368,0.316,0.299,0.301,0.324,0.290,0.303,0.297,0.300,0.291,0.293,0.296,0.308,0.292,0.292,0.312,0.336,0.296,0.290,0.313,0.342,0.311,0.314,0.285,0.451,0.301,0.303,0.316,0.290,0.281,0.282,0.276,0.271,0.271,0.286,0.285,0.278,0.284,0.284,0.278,0.274,0.309,0.281,0.280,0.289,0.311,0.311,0.336,0.313,0.294,0.324,0.354,0.353,0.324,0.335,0.353,0.327,0.315,0.322,0.297,0.296,0.313,0.351,0.294

# server warm latency
requests: 100
average_ms: 0.492
p95_ms: 0.671
raw_ms:
0.581,0.581,0.515,0.494,0.457,0.464,0.589,1.225,1.151,0.521,0.459,0.529,0.473,0.490,0.477,0.477,0.434,0.492,0.446,0.662,0.498,0.468,2.390,0.483,0.465,0.460,0.451,0.431,0.481,0.439,0.444,0.427,0.421,0.671,0.646,0.747,0.423,0.422,0.402,0.424,0.388,0.376,0.380,0.408,0.439,0.424,0.501,0.478,0.479,0.442,0.381,0.370,0.383,0.448,0.394,0.424,0.466,0.437,0.458,0.457,0.391,0.801,0.469,0.436,0.424,0.440,0.430,0.429,0.411,0.403,0.390,0.408,0.435,0.414,0.378,0.383,0.398,0.393,0.372,0.415,0.385,0.379,0.380,0.377,0.418,0.446,0.406,0.455,0.436,0.455,0.558,0.506,0.598,0.462,0.479,0.416,0.401,0.461,0.497,0.473
```


First request latency
Host/function: 0.001133s
Server: 0.002008s
```bash

~/Documents/School/ITC 531/Module 4/module_4/myshapes
❯ curl -o /dev/null -s -w "first_function_request: %{time_total}s\n" \
        -X POST http://127.0.0.1:8011/invoke \
        -H "Content-Type: application/json" \
        -d '{"name":"Alice","shout":false}'

first_function_request: 0.001133s

~/Documents/School/ITC 531/Module 4/module_4/myshapes
❯ curl -o /dev/null -s -w "first_server_request: %{time_total}s\n" \
        -X POST http://127.0.0.1:8010/greet \
        -H "Content-Type: application/json" \
        -d '{"name":"Alice","shout":false}'

first_server_request: 0.002008s
```

This data tells us that the extra layer for the host and handler adds noticeable extra letency. 
This will hold true on a server as well, and it should be kept in mind.
On the other hand, a hosted server has very efficient tooling for this kind of thing and it could be less noticible.