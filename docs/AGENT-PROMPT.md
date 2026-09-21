# Prompt: learn a product from its demo videos

Replace `<product>` and the folder path, then give this to your agent.

```
I want you to learn <product> from its demo videos so you can explain any feature, answer questions about how it works, and describe how <product> demonstrates it.

The videos are already processed into text and images with ctxr. Everything is in <folder>. Read README.md there first; it explains the layout. INDEX.md lists every video with date, length and a link to its folder.

How to study one video:
1. Open its README.md. The header gives the title, YouTube link, date, length and the official description. The Walkthrough is the video itself in order: one section per distinct screen, each with a timestamp, the frame image, and the narration spoken while that frame was on screen.
2. Look at every frame, not just the text. The frames show the real UI: menu names, button labels, layouts, chart types, settings. The narration explains intent. Treat the frames as ground truth for what the product looks like and the narration as the explanation of why. Transcripts are automatic and can mishear product terms; when text and screen disagree, trust the screen.
3. A section marked "(no narration)" is a quick screen change or a pause. Still look at the frame; it often shows the result of the previous action.
4. For exact timing or raw words, use manifest.json (frames with their aligned transcript segments) or transcript.txt.

Work through the videos in date order, oldest first, so later demos build on earlier ones. ALL-DEMOS.md contains every walkthrough in one file if you prefer to read straight through.

While you read, keep notes. For each video write a short entry: what the feature is, the problem it solves, the exact steps shown (with UI labels as they appear in the frames), what the end result looks like, and any limits the presenter mentions. Cite the video title and timestamp for anything specific, for example "Comments on dashboards, 01:40".

When you have gone through everything, produce:
1. A feature map grouped by product area, one paragraph per feature with links to the demos that cover it.
2. A glossary of the terms <product> uses, each defined in one or two sentences in its own wording.
3. Observations on how <product> runs a demo: typical length, structure, how they open, how they show before and after, what they choose to put on screen. Keep this factual and grounded in the videos.

Rules: do not invent features or details that are not in the frames or transcripts. If something is unclear, say so and point to the timestamp. Prefer plain language.
```
