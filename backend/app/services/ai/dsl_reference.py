"""Compact reference of the VideoSpecification DSL, written for an LLM
prompt (see bedrock_specification_generator.py) rather than for humans.
Lists only the element/action types that actually have a working Manim
renderer today - see animation_engine/components/registry.py - so the
model never produces something that's schema-valid but un-renderable.
"""

DSL_REFERENCE = """
You output ONLY a single JSON object (no markdown fences, no commentary before or after) shaped
exactly like this:

{
  "title": "<punchy on-screen title, <=45 chars>",
  "scenes": [ <Scene>, <Scene>, ... ]
}

Narration is written PER SCENE (each Scene has its own "narration" field - see below), NOT as one
combined script. This is a hard requirement, not a style choice: the audio for a scene's narration
is synced to play alongside THAT scene specifically, so narration written for scene 3 must actually
describe what scene 3 shows, not the video as a whole out of order.

*** NARRATION-TO-ACTION PACING IS HARD-ENFORCED (schema-validated) - THIS IS THE #1 CAUSE OF
AUDIO/VIDEO GOING OUT OF SYNC. *** Spoken narration takes roughly 2.5 words per second (~150
words/minute). A scene's "narration" word count must roughly match that scene's OWN actions' total
duration+wait_after - not the video's total length, not neighboring scenes' pacing, just this one
scene's. Concretely: (words in this scene's narration) / 2.5 must land within roughly 0.35x-1.8x of
(sum of this scene's actions' duration + wait_after). If a scene has a lot to say, give it MORE
actions/longer wait_after so the visuals have time to match, or split the explanation across two
scenes; if a scene has fast/short actions, keep its narration brief - don't write three sentences of
narration for a 3-second scene, and don't write one short sentence for a 20-second scene. A scene can
have empty/no narration if it's purely visual (e.g. a quick transition) - that's fine and doesn't
need to satisfy the ratio.

SCENE
  {"id": "<unique_snake_case_id>", "type": "generic", "duration": <seconds, number>, "narration": "<this scene's own spoken narration, or omit/null if this scene has none - see pacing rule above>", "elements": [ <Element>, ... ], "actions": [ <Action>, ... ]}
  - The user message tells you the minimum scene count to aim for based on the requested duration -
    always at least an intro (title/subtitle) and an outro, with everything between them as
    "concept" scenes that actually visualize the topic step by step with real motion (see TIMELINE &
    MOTION below - static scenes with 2-3 actions are not acceptable). Each scene's `duration` should
    roughly cover its actions' total duration+wait_after. All scene durations together should land
    near the requested total video duration.
  - For a long requested duration, fill the time with MORE scenes covering more real sub-steps,
    worked examples, or edge cases of the topic - never by stretching a handful of scenes with
    artificially long `wait` actions or slow-motion padding. A 5-10 minute video should feel like a
    thorough walkthrough with several concrete examples, not a 90-second video played in slow motion.
  - *** SCENES DO NOT SHARE STATE. *** Every scene starts from a blank canvas: only elements listed
    in THAT scene's own "elements" array exist during it, and everything is wiped before the next
    scene starts. An element created in scene 1 is GONE in scene 2, even if it has the same id.
    Consequences:
      * An action's "target" (and "into_element_id") must reference an id declared in that SAME
        scene's "elements" list - referencing an id from a different scene is invalid, full stop.
      * If a concept needs continuous back-and-forth motion (e.g. a highlight rectangle sliding
        across an array, two pointers converging, a value moving around), do the ENTIRE motion
        inside ONE scene using several move/shift actions in sequence - do not spread it across
        multiple scenes expecting the moving element to still be there.
      * If the same visual (e.g. the same array) needs to reappear in a later scene, declare a new
        element for it in that scene's "elements" list (a fresh id is fine, or reuse the same id -
        ids only need to be unique WITHIN one scene) and rebuild it with create/show, exactly as if
        it had never existed before - because it hasn't, yet, in that scene.

LAYOUT - THE SCREEN IS SMALL, OVERLAP AND OFF-SCREEN CONTENT ARE THE #1 FAILURE MODE.
  Coordinates are {"kind":"coordinate","x":<number>,"y":<number>}, origin at screen center.
  Valid range is STRICTLY enforced: x in [-6.5, 6.5], y in [-3.6, 3.6] - anything outside this is
  REJECTED. Stay well inside that, not at the edges. There are exactly FOUR vertical zones, with NO
  gap between them - every y-coordinate you use must fall inside one of these four ranges, never
  between them (y=0.0, y=2.5, and y=-2.5 are NOT in any zone and are a common source of overlap
  bugs - don't use them):
    - Title zone:   y = 3.0 to 3.5    (center y=3.25) - title/subtitle ONLY, nothing else ever goes here
    - Content-upper: y = 0.1 to 2.9   (center y=1.5)  - the main visual: array, shapes, primary diagram
    - Content-lower: y = -2.9 to -0.1 (center y=-1.5) - secondary visual: code_block, a second array/diagram
    - Caption zone: y = -3.5 to -3.0  (center y=-3.25) - ONE short caption/result text at a time, nothing else
  Default to the exact center y-value for each zone (3.25 / 1.5 / -1.5 / -3.25) unless you have a
  specific reason to shift within the zone's range. Content-upper and Content-lower are each exactly
  tall enough for a maximum-size code_block (see below) - if you place one there, it fills that zone
  and nothing else may share it until the code_block is hidden.
  Rules that prevent the overlap/overflow bugs seen in practice:
    - At most ONE element occupies each zone at a time within a scene. If you need a second thing
      in the same zone, fade_out/hide the first one before creating the second.
    - Keep on-screen text SHORT: captions/result text <=40 characters, titles <=45, subtitles <=55.
      Long text at a large font_size runs off the sides - if you need more words, lower font_size
      (text: 24-32, subtitle: 24-28) or split it across two sequential text elements, not one long one.
    - An array's on-screen width is roughly `len(values) * cell_size * 1.15` units - keep this under
      11 (e.g. <=8 values at cell_size=1.0, or fewer values at a larger cell_size) so it doesn't run
      off the left/right edges at x=0.
    - code_block size is a HARD-ENFORCED limit (schema-validated, not a suggestion) on BOTH line
      count and longest-line length together, calibrated against the real renderer - a code_block
      that violates this is REJECTED outright, not just visually ugly:
        font_size 24 (default): at most 5 lines, longest line at most ~33 characters
        font_size 20:            at most 6 lines, longest line at most ~40 characters
        font_size 18:            at most 6 lines, longest line at most ~45 characters
        font_size 16:            at most 7 lines, longest line at most ~50 characters
      A real 11-line pseudocode block at font_size 24 rendered ~5.5 units tall - nearly the whole
      frame - and overlapped every other element regardless of where it was positioned. If real
      pseudocode needs more than this, either shorten it to the essential lines only (drop
      boilerplate, use short variable names) or split it across two sequential scenes (e.g. "setup"
      then "loop body"), each within these limits - never one oversized block.
    - Rectangles/circles used as highlight overlays (e.g. a "window") should be sized to roughly
      match what they're highlighting (a window over one array cell approx. cell_size wide), not larger.

ELEMENTS (only these types exist - do not invent others).
Colors are a hex string like "#3B82F6" or one of: white,black,red,green,blue,yellow,orange,purple,pink,teal,gray,gold,maroon.

  {"type":"title","id":"...","content":"...","font_size":48,"color":"white"}
  {"type":"subtitle","id":"...","content":"...","font_size":28,"color":"gray"}
  {"type":"text","id":"...","content":"...","font_size":30,"color":"white","position":<coordinate>}
  {"type":"paragraph","id":"...","content":"...","font_size":26,"color":"white","line_width":9}
    - "paragraph" word-wraps to `line_width` (units) automatically - use it for a sentence or two of
      recap/summary text, not a single short label (use "text" for that instead). Content over ~100
      characters at the default line_width=9/font_size=26 wraps to 3+ lines and can overflow its
      zone - this is HARD-ENFORCED (schema-validated): keep content to roughly 2-3 short sentences
      at most, or lower font_size / raise line_width for more room.
  {"type":"label","id":"...","content":"...","target":"<element id this annotates>","font_size":22,"color":"white"}
  {"type":"rectangle","id":"...","width":1.5,"height":1.0,"color":"white","fill_opacity":0,"position":<coordinate>}
  {"type":"circle","id":"...","radius":0.5,"color":"white","fill_opacity":0,"position":<coordinate>}
  {"type":"line","id":"...","start":<coordinate>,"end":<coordinate>,"color":"white"}
  {"type":"arrow","id":"...","start":<coordinate>,"end":<coordinate>,"color":"yellow","label":"optional"}
  {"type":"array","id":"...","values":[<numbers or short strings, 1-8 items>],"cell_size":1.0,"color":"white","position":<coordinate>}
  {"type":"pointer","id":"...","target":"<array element id>","index":0,"label":"i","color":"yellow"}
  {"type":"code_block","id":"...","language":"python","lines":["line one","line two", "..."],"font_size":22,"position":<coordinate>}

ACTIONS (only these types exist). Every action may have "target" (an element id, or a list of
element ids, referencing elements declared EARLIER in the SAME scene's "elements" list - never a
different scene), "duration" (seconds, default 1.0, max 60), and "wait_after" (seconds, default 0).
Actions in a scene play in order, one after another - see TIMELINE & MOTION below.

*** ELEMENT TYPES AND ACTION TYPES ARE TWO COMPLETELY SEPARATE VOCABULARIES - NEVER MIX THEM. ***
An action's "type" can ONLY be one of the exact action names listed below (create, show, hide,
write, fade_in, fade_out, move, shift, scale, rotate, highlight, unhighlight, transform, wait,
draw_arrow, move_pointer, swap_elements, update_text, highlight_code_line, camera_zoom, camera_pan).
There is NO action named "text", "title", "array", "arrow", "circle", "rectangle", "code_block", etc
- those are ELEMENT types, valid only inside the "elements" list, never as an action's "type".
An action can only animate/reveal/modify an element that ALREADY EXISTS in that scene's "elements"
list - it can never introduce a brand new element on its own. If something new needs to appear
partway through the timeline, you must still declare it up front in "elements" (nothing forces it
to be visible immediately - elements are invisible until a create/show/write/fade_in action reveals
them), then reveal it at the right moment with one of the real action types above.

  {"type":"create","target":["id1","id2"],"duration":1.0}        - animated draw-in
  {"type":"show","target":["id1"]}                                 - instant appear
  {"type":"hide","target":["id1"]}                                 - instant disappear
  {"type":"write","target":["id1"],"duration":1.0}                - animated handwriting (good for text/title/code)
  {"type":"fade_in","target":["id1"],"duration":0.8}
  {"type":"fade_out","target":["id1","id2"],"duration":1.0}
  {"type":"move","target":["id1"],"to":<coordinate>,"duration":1.0}
  {"type":"shift","target":["id1"],"dx":1.0,"dy":0,"duration":1.0}
  {"type":"scale","target":["id1"],"factor":1.5,"duration":0.6}
  {"type":"rotate","target":["id1"],"angle_degrees":90,"duration":0.6}
  {"type":"highlight","target":"arr1","index":2,"color":"yellow","duration":0.4}   - index is an array cell (0-based, must be < the array's length)
  {"type":"unhighlight","target":"arr1","index":2,"duration":0.3}
  {"type":"transform","target":["id1"],"into_element_id":"id2","duration":0.8}     - morphs id1 into id2's shape; id2 must be a declared element
  {"type":"wait","duration":0.5}                                                    - no target
  {"type":"draw_arrow","target":["arrow_id"],"duration":0.6}
  {"type":"move_pointer","target":"ptr1","index":3,"duration":0.5}                 - index must be < the target array's length
  {"type":"swap_elements","target":"arr1","index_a":0,"index_b":3,"duration":0.6}  - both indices must be < the array's length
  {"type":"update_text","target":"id1","new_text":"new content","duration":0.5}
  {"type":"highlight_code_line","target":"code1","line_number":2,"color":"yellow","duration":0.3} - 0-indexed, must be < number of lines in that code_block
  {"type":"camera_zoom","scale":0.6,"duration":1.0}    - <1 zooms in, >1 zooms out; if you zoom in, zoom back out later in the same scene
  {"type":"camera_pan","to":<coordinate>,"duration":1.0}

TIMELINE & MOTION - think of a scene's "actions" list as a strict timeline: each action starts the
instant the previous one (plus its wait_after) finishes, nothing plays concurrently. To make videos
feel animated instead of static:
  - Every concept scene needs VISIBLE MOTION, not just fades: prefer highlight/move_pointer/shift/
    swap_elements/highlight_code_line sequences over static create-then-wait-then-fade_out. A scene
    that just creates elements and fades them out with no motion in between is not acceptable.
  - Break one big idea into several small steps (3-8 short actions of 0.3-0.8s each) rather than one
    or two long ones - this is what makes motion read as deliberate instead of rushed.
  - Use camera_zoom for emphasis on the key moment of a scene (zoom in approx. 0.5-0.7, hold, zoom back out
    to 1/that value before the scene ends) and camera_pan when the focus genuinely moves across the
    screen (e.g. following a pointer far from center).
  - Sync code_block and array/pointer actions: highlight_code_line the relevant line at roughly the
    same moment the corresponding visual action happens, so the code and the animation narrate the
    same step together.
  - Every element you create should also be dismissed (fade_out/hide) before its scene ends, so nothing
    lingers into whatever visually replaces it.
  - CONCEPTUAL points (rules, common mistakes, recognition signals, problem patterns, complexity,
    variations) are the easiest place to accidentally under-animate, because they don't have an
    obvious "thing that moves" - but their narration still takes real time to speak, and if the
    actions for that scene are too short, the audio for that point ends up playing over whatever
    scene comes NEXT (a real sync bug - see NARRATION-TO-ACTION PACING). Fix this by giving each
    sub-point its OWN element and OWN action with a real wait_after, one at a time, instead of one
    text block sitting on screen while narration talks over it for a long time:
      * Rules/mistakes/patterns: write/fade_in each one as a separate short text line, in sequence
        (e.g. 3 rules = 3 text elements + 3 write actions, each with ~1-2s wait_after) - this alone
        can easily cover 10-20s of real action time instead of one static screen.
      * Recognition signals: show the signal text, then fade_in a "-> use this technique" arrow/label
        pointing at it, one at a time if there are multiple signals.
      * Complexity: write the Big-O text, then highlight/underline the part of the code or loop
        structure that justifies it, with a wait_after to let that land before moving on.
    The goal: the scene's total action+wait_after time should roughly match how long its own
    narration takes to say (~2.5 words/second) - pad with MEANINGFUL sequential reveals of real
    content, never with a long silent wait on an unchanging screen.

EXAMPLE - a moving highlight window over an array with synced code, entirely within one scene, that
follows the layout zones and has real step-by-step motion (this pattern covers sliding window, two
pointers, binary search range, and similar "something moves across the array" topics). Note the
narration: 13 words / 2.5 = ~5.2s, and the actions below total ~5.3s - that's the pacing match to aim
for on every scene.
  "narration": "Watch the window slide across the array, growing the sum as it goes.",
  "elements": [
    {"type":"array","id":"arr1","values":[2,1,5,1,3,2],"cell_size":1.0,"color":"white","position":{"kind":"coordinate","x":0,"y":1.5}},
    {"type":"rectangle","id":"window","width":2.0,"height":1.0,"color":"yellow","fill_opacity":0.25,"position":{"kind":"coordinate","x":-2.0,"y":1.5}},
    {"type":"code_block","id":"code1","lines":["window_sum = sum(arr[0:2])","window_sum += arr[i] - arr[i-k]"],"font_size":22,"position":{"kind":"coordinate","x":0,"y":-1.5}}
  ],
  "actions": [
    {"type":"create","target":["arr1"],"duration":0.8},
    {"type":"create","target":["code1"],"duration":0.6},
    {"type":"fade_in","target":["window"],"duration":0.5},
    {"type":"highlight_code_line","target":"code1","line_number":0,"color":"yellow","duration":0.3},
    {"type":"wait","duration":0.4},
    {"type":"shift","target":["window"],"dx":1.0,"dy":0,"duration":0.6},
    {"type":"highlight_code_line","target":"code1","line_number":1,"color":"yellow","duration":0.3},
    {"type":"shift","target":["window"],"dx":1.0,"dy":0,"duration":0.6},
    {"type":"shift","target":["window"],"dx":1.0,"dy":0,"duration":0.6},
    {"type":"fade_out","target":["arr1","window","code1"],"duration":0.6}
  ]

HARD RULES (violating any of these makes the whole output invalid):
  - Every element "id" is unique within its scene.
  - Every action "target" id (and every "into_element_id") must reference an element declared
    earlier in that same scene's "elements" list - NEVER an id from a different scene (see above).
  - Every coordinate's x is in [-6.5, 6.5] and y is in [-3.6, 3.6] - no exceptions.
  - "index" on highlight/unhighlight, and "index_a"/"index_b" on swap_elements, must be less than
    the length of the target array's "values".
  - "index" on move_pointer must be less than the length of the array the target pointer points at.
  - "line_number" on highlight_code_line must be less than the number of lines in the target code_block.
  - Do not use any element or action type not listed above.
  - NEVER output null/None for any field. Every "array" element's "values" must be a full list of
    actual numbers or short strings (no null entries) matching its declared length. Every
    "update_text" action's "new_text" must be an actual non-empty string, never null - if you don't
    know what to write, use a short literal like "done" rather than omitting it or writing null.
  - Each scene's own "narration" word count / 2.5 must be within 0.35x-1.8x of that scene's own
    actions' total duration+wait_after (see NARRATION-TO-ACTION PACING above) - a scene whose
    narration would take much longer or shorter to speak than its actions take to play is rejected.
""".strip()
