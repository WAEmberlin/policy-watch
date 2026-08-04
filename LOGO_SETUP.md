# Logo Setup Instructions

## Logo File Location

The logo image should be placed in the `docs/` directory with the filename `PolicyWatch Logo.png`.

**Full path**: `docs/PolicyWatch Logo.png`

## File Requirements

- **Filename**: `PolicyWatch Logo.png` (must be exactly this name)
- **Location**: `docs/` directory (same folder as `index.html`)
- **Format**: PNG recommended (JPG and SVG also work)
- **Size**: Recommended height around 60px (width will scale automatically)

## How to Add Your Logo

1. **Prepare your logo image**
   - Save it as `PolicyWatch Logo.png`
   - Recommended: 60px height, transparent background if possible

2. **Place the file**
   - Copy `PolicyWatch Logo.png` to the `docs/` folder
   - The file structure should look like:
     ```
     docs/
       ├── index.html
       ├── hearings.html
       ├── script.js
       ├── site_data.json
       └── PolicyWatch Logo.png  ← Your logo goes here
     ```

3. **Verify it works**
   - The logo will appear in the header on:
     - Main page (`index.html`)
     - Hearings page (`hearings.html`)
   - If the logo doesn't appear, check:
     - File is named exactly `PolicyWatch Logo.png` (case-sensitive, with spaces)
     - File is in the `docs/` directory
     - File is a valid image format

## Current Status

The HTML is already configured to display the logo. The file `PolicyWatch Logo.png` should already be in the `docs/` directory and will appear on all pages.

## GitHub Pages

When you commit and push to GitHub:
- The logo file will be included in the repository
- It will be served from GitHub Pages at: `https://[your-username].github.io/policy-watch/PolicyWatch%20Logo.png`
- The website will automatically display it

## Troubleshooting

**Logo not showing?**
- Check the browser console for 404 errors
- Verify the file is named exactly `PolicyWatch Logo.png` (case-sensitive, with spaces)
- Ensure the file is in the `docs/` directory
- Try clearing your browser cache
- Note: GitHub Pages URLs encode spaces as `%20`, but the HTML reference should use the actual filename with spaces

**Logo too large/small?**
- The CSS sets height to 60px
- Adjust the height in `docs/index.html` and `docs/hearings.html`:
  ```css
  .logo {
      height: 60px; /* Change this value */
  }
  ```

