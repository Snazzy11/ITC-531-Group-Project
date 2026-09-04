Campus Lost and Found Application
Our project idea is to make a campus lost and found application in which students at a campus can login and authenticate with a student email. 

Once logged in students will be able to submit a missing item request with an optional picture as well as a description including color, location thought to be lost at, and other key descriptions.

Students will also be able to submit that they have found lost items by taking a picture of them and filling out a description. 

When either of these events happen asyncronously a python worker will try and match possible lost and found items and notify a student if their lost item may have been found.

This includes each of the key requirments of the project. It involves a fastAPI app to expose endpoints which will be used during each of these actions. It involves a database which will store nessasary data. It involves async operations triggered by a message broker so that the item search can happen in the background and the student will still be able to use that app and just get notified when the query is finished.