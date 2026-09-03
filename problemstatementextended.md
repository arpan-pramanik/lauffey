What to build
A pipeline that takes a face scan as input, identifies matching content on the web/social media, and then verifies that discovered data using a blockchain — end to end. Pipeline shape: Face scan input → Web/social media search (find matching post) → Blockchain upload/verification of the discovered data
Technical requirements
Face identification Detect and encode a face from an input image (any face detection/recognition library or API is acceptable).


Social media / web search Use the face to search the web and find at least one real, matching social media post (via reverse image search, an API, or a scripted search approach). This should be a genuine search step, not a hardcoded/pre-picked result.


Blockchain verification Once a matching post is found, upload the post (or a hash/fingerprint of it, e.g. the image, text, or metadata) to a blockchain to create a verifiable, tamper-evident record. Any blockchain may be used — public testnet, mainnet, or a local/simulated chain — as long as you can demonstrate re-verifying the data against the on-chain record.


No website required You do not need to build or host a project website. Focus your time on the pipeline itself.


GitHub repo required Your full source code must be in a GitHub repo, with a README covering what the project does, how to run it, which blockchain you used, and any known limitations.


