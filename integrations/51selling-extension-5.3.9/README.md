# 51Selling Extension 5.3.9

This is the unpacked extension copy used by the local Chrome profile. It is
kept in the ERP repository so changes are reviewable and recoverable.

## ERP recollection tab behavior

Amazon URLs opened for ERP recollection use the marker
`#meli-recollect-source=<source-product-id>`. The extension closes that tab
only after the product-save endpoint returns `IsSuccess === true`. Failed,
timed-out, duplicate-confirmation, and human-verification flows leave the tab
open for diagnosis or retry. Ordinary Amazon collection URLs are unchanged.

After changing this unpacked copy, reload it from `chrome://extensions` before
live verification.
