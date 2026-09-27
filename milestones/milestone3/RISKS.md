
### Risk 1: Cold start
- What goes wrong: A lone user makes a request that causes a cold start of everything
- Component: Any of our functional and container-on-demand containers
- Trigger: An user request at an unusual time
- Signal and where: If we logged total request round trip time, we would likely see this in the 1% highs. Also, any sudden burst of logs compared to quiet time
- Response: This one doesn't have much of a way to mitigate it without making an monolith app. Even the 1% high for this kind of app doesn't have much of an effect though.

### Risk 2: Erasure of state on recycle
- What goes wrong: We lose state on recycle
- Component: API
- Why? The assignment asked to find a state entry we got wrong. We actually did get one wrong. The state column for API said it needed state to store data. We forgot to change it to say it doesnt need state, because the database is its own container. The API should be dumb, and only direct work to other places.
- We should have full backups every once in a while to prevent ANY data loss

### Risk: Concurrency limits
- What goes wrong: Too many connections to the database accross the various places in code
- Component: The database container
- Trigger: We try to have too many functions running and connections open at once
- Signal and where: The database container will starting logging errors; we SHOULD direct these to our logger but it will be visible in the database nonetheless. Also, functions will start erroring out and HTTP error codes will start being returned.
- Response: Optimize our code. SQLAlchemy should handle this kind of thing already, but we might need to implement some extra code to prevent this from happening and handle it smoothly.

### Risk 4: No match in reasonable time
- What goes wrong: There is high demand all at once (lots of searches happening); there is a queue of even more things already
- Component: A combination of all of them, but particularly the matcher
- Trigger: A larger-than-expected influx of users
- Signal and where: We would see maximum CPU useage from the matcher, possibly a database backlog, and probably not much in the log unless we periodically log the queue size
- Response: Increase the server size, or focus on only new matches during that time (any operation-reducing heuristic that applies only during peak hours would work)


# Final reversal decision
If any change would be made, it would probably be the functional image worker to instead be a container on demand and be turned into a batched job (with a maximum wait time)
The cause for this would be if asking the server to do this job costs too much overhead or if the hoster simply doesnt have it available.
If the image worker is forced to be active more than 30% of the total server time, I would call that the treshold for switching to container on demand.
The maximum wait time could be tweaked, but I would think that if an image has been in the queue for more than 1 minute and there is still not enough to cause a container to start, one should be started no matter how many are in that queue. The wait time could be longer in off hours.