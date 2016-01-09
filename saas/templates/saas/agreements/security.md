{{organization.printable_name}} Security Policy
==========================

Maintaining an evolving service secure requires a constant re-evaluation
of risks and actions to mitigate them.

{{organization.printable_name}} does a reasonable attempt at keeping your information secure
using time tested [guidelines](http://en.wikipedia.org/wiki/Web_application_security).

If you need to report a security vulnerability or have any questions
regarding our security policy, please [e-mail our security chief](mailto:{{organization.email}})
directly.

Physical Security
-----------------

All of {{organization.printable_name}} online services are hosted at Amazon. As many well-known
major web sites, we rely on Amazon physical security to its data centers.

Backups are kept off-line off-site.

Network Security
----------------

All communications to the authenticated service are done through SSL.

We are running latest operating system distributions and install security
patches as they become available. Since you cannot hack something that
is not there, we are always on the look out to remove unnecessary packages
in the first place.

On top of Amazon security policies, each virtual machine is configured
with its own firewall with only the minimum number of ports open.

Solely the strict minimum number of {{organization.printable_name}} employees have shell
access to the {{organization.printable_name}} infrastructure.

We monitor all access and attempted access to the virtual machines
that provides {{organization.printable_name}} service.

Credit card safety
------------------

When you refill an Organization credit, we do not store any of your card
information on our servers. It's handed off to [Stripe](http://stripe.com),
a company dedicated to storing your sensitive data on [PCI-Compliant](http://en.wikipedia.org/wiki/Payment_Card_Industry_Data_Security_Standard)
servers.
