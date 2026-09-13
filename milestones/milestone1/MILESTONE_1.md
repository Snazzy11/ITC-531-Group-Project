# Project Overview
Our application, Campus Seekr, is designed to allow users around a college campus (Central Michigan Unversity's for our purposes) to report on items lost and/or found around campus with the ultimate goal of reuniting orphaned items to their rightful owners. Our userbase will consist of anyone who frequents the campus and has an interest in ensuring that items that get misplaced around campus will be returned to those to whom they belong. 

When a user loses an item, they will be able to upload relevant information to the app that may assist in locating it, such as a description of the item and its last seen location. When a user locates an item around campus, a user will be able to upload a picture of the item as well as the location it was found at. Users will be able to declare a match between an item that has been reported as lost and an item that has been reported as found.

|Service Category|Relevant Application Features|Our Proposed Vendor|
|----------------|-----------------------------|---------------|
|Object Storage|Store item photographs.|S3 API|
|Relational Data|Storing users, items, and matches.|PostgreSQL|
|Message Broker|Queue photograph processing and lost/found comparisons.|AMQP 0-9-1|
|Metrics|Expose request counts and duration, completed jobs, and processing failures.| Prometheus Exposition|

# API Endpoint Documentation

### GET /api/v1/item/{item_id}
- Description: Get 1 item by ID. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### GET /api/v1/items
- Description: Get all items (paginated, accepts filters).
- Access: Public
- Parameters: page_size: int (max of 100 items returnable, error otherwise); page_num: int (filter parameters: 'lost', 'found', item status, newere items by default)
- Response: 200 OK
- Error(s): 404 Not Found (returned list is empty)

### GET /api/v1/item/{item_id}/match
- Description: Get match by item. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found, 409 Conflict

### POST /api/v1/item
- Description: Upload an item to the application. 
- Access: Public
- Parameters: name: str, location: str
- Response: 201 Created
- Error(s): 409 Conflict

### PATCH /api/v1/item/{item_id}
- Description: Edit an existing item. 
- Access: Owner (only item uploader can edit their item)
- Parameters: id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### DELETE /api/v1/item/{item_id}
- Description: Mark an item that is not paired with a match as 'withdrawn.' 
- Access: Staff
- Parameters: id: integer
- Response: 204 No content
- Error(s): 404 Not Found

### GET /api/v1/match/{match_id}
- Description: Get 1 match by match_id as well as the item IDs involved in the match. 
- Access: Public
- Parameters: match_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/match
- Description: Create a match between two items. 
- Access: Owner (only item uploaders can declare matches between items)
- Parameters: lost_id: int, found_id:int
- Response: 201 Created
- Error(s): 404 Not Found, 409 Conflict

### DELETE /api/v1/match/{match_id}
- Description: Remove a match and mark both items as open. 
- Access: Owner (only item uploaders can remove their matches)
- Parameters: match_id: integer
- Response: 204 No content
- Error(s): 404 Not Found

### GET /api/v1/location/{location_id}
- Description: Get 1 location by location_id. 
- Access: Public
- Parameters: location_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/location
- Description: Create a location. 
- Access: Staff
- Parameters: name: str, coordinates: str
- Response: 201 Created
- Error(s): 409 Conflict

### DELETE /api/v1/location/{location_id}
- Description: Mark location is_active as false. 
- Access: Staff
- Parameters: location_id: integer
- Response: 204 No content
- Error(s): 404 Not Found
