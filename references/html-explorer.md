# Offline HTML explorer

Use the views the system needs. These patterns are not a mandatory page count:

| View | Interaction | Reader's question |
| --- | --- | --- |
| System map | Select a component and inspect its contract | What lives where and how does it connect? |
| Walkthrough | Choose a journey and move through its steps | How does setup or intent reach a result? |
| What runs | Choose a boundary and concrete case | Why does work proceed, change route or stop? |
| State and recovery | Inspect ownership and recovery diagrams | What survives and what needs reconciliation? |
| Built and remaining | Compare source, evidence and open gates | What is available at this snapshot? |
| Product areas | Select a proposed area and follow component links | Where could ownership be divided? |

The map is the main explanatory object. Use location or authority regions, labeled handoffs and a visible distinction for unconnected paths. A diagram must not imply an implemented library runs in production.

Each selected component needs its job, a local flow, input/output, execution owner, limits and source links. Include a way back to the selected node. Link component IDs from steps and area views so the reader can move between explanations.

A decision worksheet explains existing rules. Say it neither invokes the product nor inspects live state. Name earlier gates that are assumed to pass. Derive cases from code branches rather than a speculative simulation.

## Implementation

Default to one HTML file with inline CSS and JavaScript. Avoid external assets, runtime APIs, analytics and unnecessary scaffolding. Local source links are compatible with offline use when the repository accompanies the file. Inherit the project's existing visual system, or the user's selected exemplar, without copying another product's facts.

Keep factual data separate from rendering so corrections can reach every affected view. An optional JSON block enables source-link validation without executing code:

```html
<script type="application/json" id="architecture-data">
{
  "components": [
    {
      "id": "gateway",
      "name": "Command gateway",
      "sources": ["src/gateway.ts", {"path": "docs/readiness.md"}]
    }
  ]
}
</script>
```

This is a data-container example, not source content to reuse. Add the actual fields, journeys and cases. Escape data before inserting it into HTML. Resolve source links from the artifact location. Display source line numbers or symbols separately when local file viewers do not support line anchors.

Provide readable core content without JavaScript, or link a complete companion document as a clear fallback. Empty generated panels are not a fallback.

## Interaction invariants

- Tabs have matching roles, controls, labels and selected state, with one tab stop. Support arrow keys and Home/End. Keep focus on a tab when it activates; body jump links may focus a panel or inspector.
- Selection is exposed through text or ARIA as well as color. Focus remains visible.
- Detailed URLs represent the displayed state, such as `#map/gateway`, `#journey/install/3` or `#gates/delivery/uncertain`.
- Leaving and returning to a tab preserves its selection and writes that exact selection to the URL. Reload reproduces it. Malformed hashes have a safe fallback.
- Selecting a node exposes its explanation; returning restores focus to the selected map node.
- Step controls have honest first/last disabled states. Mobile controls and results remain reachable without page-wide overflow.
- Changing a category refreshes dependent cases before rendering, so stale cases cannot appear under a different boundary.
- Printing includes all content promised by the button label. A “Print reference” action should not silently print only current selections.

Use readable body measure, accessible contrast, localized scrolling for wide diagrams/tables and reduced-motion support. Verify the real long labels at mobile widths.

## Deterministic static checks

```sh
python3 <skill-dir>/scripts/check_explorer.py <repo>/AS-BUILT-ARCHITECTURE.html
```

The standard-library checker checks duplicate IDs, local links, fragments, tab/panel relationships, declared asset dependencies and explicit source fields in `architecture-data`. It does not evaluate JavaScript, fetch the network or validate architectural claims.

For generated links, export the actual rendered anchor attributes through the browser tool:

```js
JSON.stringify([...new Set(
  [...document.querySelectorAll('a[href]')]
    .map(a => a.getAttribute('href'))
)])
```

Save the returned JSON array to a temporary file and pass `--rendered-links <file>`. Decode any tool-added wrapper first. Aggregate exports across states when generated links are removed between selections. This does not require reading cookies, credentials or browser storage.

Use repeatable `--route-fragment <name>` for flat client routes verified against the page's router, such as `#evidence` when there is no element with that literal ID. Structured route hashes are reported as unvalidated routes. Browser tests must check both kinds.

Use `--site-root <dir>` to resolve root-relative web paths against a site directory; the default is the HTML file's parent directory. Explicit `file:` URLs resolve as filesystem paths. Use `--allow-assets` only when supporting assets are deliberately part of the requested output; the default checks one-file offline packaging.

## Browser checks

Use the environment's supported browser tool and instructions. Exercise the real DOM or accessible controls, not render functions. Cover each real control family, then investigate failures instead of repeatedly rerunning broad checks:

- every view, component and return control
- all steps and alternative journeys, including first/last boundaries
- every gate category and case, including refusal and uncertainty
- component, step and area cross-links
- detailed hash open/reload and selection retained after tab return
- keyboard activation followed by continued arrow-key navigation
- desktop/mobile, supported themes and reduced motion
- console errors, unexpected requests and print completeness

Keep probes, screenshots, print files and link exports in scratch storage unless requested. Report the checks actually run. Static validation or screenshot review is not exhaustive accessibility testing.
