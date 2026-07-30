# manifest-delete-recreate

The patch represents `requirements.txt` in two distinct file-change records: first as a deleted baseline file, then as a newly created file that declares the dependency imported by the accompanying source change. The recreated declaration must remain proposed, untrusted evidence and must not erase the trusted path identity.
