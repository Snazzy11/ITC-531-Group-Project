Campus Seekr - Campus Lost and Found Application

Our project idea is to make a campus lost and found application in which students at a campus can login and authenticate with a student email.

Once logged in students will be able to submit a missing item request with an optional picture as well as a description including color, location thought to be lost at, and other key descriptions.

Students will also be able to submit that they have found lost items by taking a picture of them and filling out a description.

When either of these events happen asynchronously a Python worker will try and match possible lost and found items and notify a student if their lost item may have been found.

This includes each of the key requirements of the project. It involves a FastAPI app to expose endpoints which will be used during each of these actions. It involves a database which will store necessary data. It involves async operations triggered by a message broker so that the item search can happen in the background and the student will still be able to use that app and just get notified when the query is finished.

The main user will be a college student however there will also be an admin login which will allow you to edit and remove posts.

MVP Features:

1. FastAPI Endpoints
2. Relational Database
3. Message broker running async
4. Use of S3 API
5. Authentication
6. metrics with Prometheus
7. Deployed

For an MVP to be complete the app must be able to post missing items as well as post found items and have a way to match missing items to posts.

Out Of Scope:
AI image recognition, Live chat between users, mobile app

four service categories:
S3 API: Store uploaded item photographs.
PostgreSQL wire protocol: Store users, listings, claims, potential matches.
AMQP 0-9-1: Queue background jobs that process photographs and compare lost/found listings.
Prometheus exposition: Expose request counts, request duration, completed jobs, and processing failures.

Success Criteria:

Users can create and view test lost/found posts, including photos
The app correctly matches known lost/found pairs and notifies the users
Posts and photos are still available after restarting the app
Background jobs finish after the worker is stopped and restarted
Admins can edit and remove posts, while student accounts cannot access admin features

Team Information:
Main communication channel will be Discord/messages:
Devon Burton: Cmich: burto2dr, GitHub: devBurton
Parker: Cmich: scott1pk, GitHub: Snazzy11
Doug: Cmich: varne1dm, GitHub: dmacv3

planned meetings on Friday 5PM
