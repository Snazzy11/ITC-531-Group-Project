# ITC-531-Group-Project

# Technologies used

- Python package management will be done with uv
  - Make sure you run uv init and uv sync upon pulling the repo

# Developers

- Parker Scott 
- Devon Burton 
- Doug Varney

## Roles

Developer roles will be rotated every week.
The roles are: Project Lead, Backend Engineer, DevOps Engineer, Documentation Lead

Each role is NOT assigned because that person is supposed to do all that work for a given week. Everyone is always responsible for every task, and we all review each other. Instead, a role assignment just means that that individual should be “checking up on” their domain.

For week 1: These are the role assignments

- Devon
  - DevOps Engineer  
- Parker
  - Project Lead
- Doug
  - Backend Engineer
  - Documentation Lead

# Running the Service
1. Clone the repository:
```git clone https://github.com/Snazzy11/ITC-531-Group-Project```
2. Build and run the container:
```docker compose -up -d --wait```
3. Teardown:
```docker compose down --volumes```

# Contributing Code

## Pre-requisites

* Make sure you already have git ssh and authentication set up 
* You need to be in the repo as a collaborator

## Instructions

1. Create a branch from main
   1. This lets you make any changes you want, without possibility of destroying main
2. Make some changes, and commit them
   1. You should make incremental commits, so you have places to go back to if you change code
3. Feel free to push your branch at any time, but only make a pull request when it is read
4. Once your feature is complete, create a pull request on GitHub
5. This will require approval from at least 1 reviewer
6. Once approved, merge the branch

## Decisions
The concept we will pursue is a lost and found system for the campus community. Users will be able to upload images of items they find around campus as well as the locations they found them out and/or descriptions of lost items and last seen locations.

We decided not to pursue features that could benefit this application such as: such as AI image recognition to identify items, a live messaging system between users, or a mobile application. While all these features would make for a better user experience and would contribute greatly to the app's usability, they remain out of scope for the purposes of this project. 