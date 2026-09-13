# Part 1
#@ Project Overview
Our application, Campus Seekr, is designed to allow users around a college campus (Central Michigan Unversity's for our purposes) to report on items lost and/or found around campus with the ultimate goal of reuniting orphaned items to their rightful owners. Our userbase will consist of anyone who frequents the campus and has an interest in ensuring that items that get misplaced around campus will be returned to those to whom they belong. 

When a user loses an item, they will be able to upload relevant information to the app that may assist in locating it, such as a description of the item and its last seen location. When a user locates an item around campus, a user will be able to upload a picture of the item as well as the location it was found at. Users will be able to declare a match between an item that has been reported as lost and an item that has been reported as found.

|Service Category|Relevant Application Features|Our Proposed Vendor|
|----------------|-----------------------------|---------------|
|Object Storage|Store item photographs.|S3 API|
|Relational Data|Storing users, items, and matches.|PostgreSQL|
|Message Broker|Queue photograph processing and lost/found comparisons.|AMQP 0-9-1|
|Metrics|Expose request counts and duration, completed jobs, and processing failures.| Prometheus Exposition|

# Part 2
**API Endpoint Documentation**

Note: Staff has access to all endpoints listed. When staff is stated explicitly it menas staff only

## Items

### GET /api/v1/items/{item_id}
- Description: Get 1 item by ID. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### GET /api/v1/items
- Description: Get all items (paginated, accepts filters). Default sort it `created_at` descending
- Access: Public
- Parameters: page_size: int (max of 100 items returnable, error otherwise); page_num: int (filter parameters: 0|1 \[lost|found\], array of allowed item statuses, location by id, sort type)
- Response: 200 OK
- Error(s): 422 if field is missing or invalid

### GET /api/v1/items/{item_id}/matches
- Description: Get match by item. 
- Access: Public
- Parameters: item_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/items
- Description: Upload an item to the application. 
- Access: Public
- Parameters: name: str, type: int, location_id: int, description: str|None
- Behavior: Status is created as 'open' and created_at is set automatically
- Response: 201 Created and returns item
- Error(s): 422 if missing or incorrect field and data about error; 409 Conflict for duplicates; 404 if location_id doesnt exist

### PATCH /api/v1/items/{item_id}
- Description: Edit an existing item. 
- Access: Owner (only item uploader can edit their item)
- Parameters: id: integer; name, description, location_id can all be updated by Owners, status can be changed to withdrawn; only Staff can change type or status otherwise
- Response: 200 OK and the updated item
- Error(s): 422 if malformed; 404 Not Found if id is wrong

### DELETE /api/v1/items/{item_id}
- Description: Mark an item that is not paired with a match as 'withdrawn'. Does not truly delete
- Access: Owner
- Parameters: id: integer
- Response: 204 No content
- Error(s): 409 if item is part of a match (make this explicitly clear); return 204 if not found

## Matches
### GET /api/v1/matches/{match_id}
- Description: Get 1 match by match_id as well as the item IDs involved in the match. 
- Access: Public
- Parameters: match_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/matches
- Description: Create a match between two items. 
- Access: Owner (only uploaders of 'lost' items can declare matches between items)
- Parameters: lost__item_id: int, found_item_id:int
- Response: 201 Created and the match item
- Error(s): 404 Not Found for incorrect ids, 422 if ids dont match to items correctly, 409 Conflict if items are already in matches or if status is not open

### DELETE /api/v1/matches/{match_id}
- Description: Remove a match and mark both items as open. 
- Access: Owner (only item uploaders can remove their matches)
- Parameters: match_id: integer
- Behavior: Status reset is done in Python. 
- Response: 204 No content
- Error(s): None, return 204 if not found


## Items
### GET /api/v1/locations/{location_id}
- Description: Get 1 location by location_id. 
- Access: Public
- Parameters: location_id: integer
- Response: 200 OK
- Error(s): 404 Not Found

### POST /api/v1/locations
- Description: Create a location. 
- Access: Staff
- Parameters: name: str, coordinates: str, description: str
- Behavior: Auto-set is_active to true
- Response: 201 Created
- Error(s): 409 Conflict if duplicate; 422 if required field missing

### DELETE /api/v1/locations/{location_id}
- Description: Mark location is_active as false. 
- Access: Staff
- Parameters: location_id: integer
- Response: 204 No content
- Error(s): None, return 204 if not found


# Part 4
## Database / resource description
* Item  
  * Item is what the whole application is designed around. It is either something someone lost and posted, or something someone found and posted  
    * If somebody lost something, there doesn't need to be a full "found" post as well, and vice versa. That could be the case, but more likely someone files a "claim" which automatically generates a new item entry, and then a match  
    * Attributes  
      * id (the item id; integer)  
      * name (what the item is called; string) \[could implement specific types later, like 'keys', 'phone', 'other'\]  
      * description (description of the item and details about it; string)  
      * type (lost '0' or found '1'; integer) \[constrained to 0 or 1\]  
      * status (where the item is in its life; string) \[constrained to 'open', 'matched', 'returned', 'withdrawn', or 'expired'; defaults to 'open'\]  
      * location\_id (foreign key; integer)  
      * user\_id (to be implemented later; would be foreign key integer)  
      * tags (to be implemented later; JSON type or array) \[this would enhance matching functionality for users\]  
      * created\_at (date the item was posted; Date type)  
    * Deletion Behavior  
      * Restrict deletions when a match exists. A match means an item got paired with another item, so deleting one side shouldn't erase the other side  
      * "Deleting" a post should normally just set the status to 'withdrawn' and hide it from search. Real deletion is for admin cleanup and spam.  
      * Because the rule is a foreign key constraint, the database enforces it instead of just code. The API can still check for matches first just to give a nicer error than a 500\.  
  * Match  
    * A match is for when someone who lost an item gets matched with someone who found one.  
    * Matches is its own database table, with a match ID, and then 2 item ids (one lost and one found)  
    * Attributes  
      * id (the match id; integer)  
      * lost\_item\_id (foreign key; integer) \[must point at a type '0' item\]  
      * found\_item\_id (foreign key; integer) \[must point at a type '1' item\]  
      * created\_at (date of the match; Date type)  
    * Constraints  
      * The same two items can't be matched twice, and an item can't match itself.  
      * Whether each id points at the right type has to be checked by whatever creates the match, since the database can't check across rows.  
    * Deletion Behavior  
      * Matches can be deleted freely. Deleting a match doesn't touch either item, it just means the two are no longer paired.  
      * Deleting a match should put both items back to 'open', and that needs to be enforced in python  
  * Location  
    * Location is literally a location  
    * I.e. the School of Music; Pearce Hall; Dine and Connect  
    * Each can have some optional data about it, but a location name and coordinate are whats required.  
    * Attributes  
      * id (the location id; integer)  
      * name (name of the location; string)  
      * coordinates (the coordinates of the location; string)  
      * description (optional data about the location; string)  
      * is\_active (whether the location still shows up when posting; boolean)  
    * Deletion Behavior  
      * Restrict deletions when the items exist. Locations will rarely just 'disappear', and we don't want to delete orphan items just because of the location not existing.  
      * Buildings *can* get renamed or closed, so we can retire a location by setting is\_active to false. Old posts can keep using it, but new posts cant

## Database models
Models can be found in code in models.py