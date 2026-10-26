import type { SessionView } from "../../api/client";
import { Icon } from "../../app/Icon";

const names: Record<string, string> = {
  bag: "Bag",
  phone: "Phone",
  wallet: "Wallet",
  keys: "Keys",
};
export function CaseSummary({ session }: { session: SessionView | null }) {
  const fields = session?.fields;
  const values = [
    ["Item", fields?.category ? names[fields.category] : null],
    ["Colour", fields?.colour],
    ["Last seen", fields?.location],
    ["Date lost", fields?.lost_date],
    ["Brand", fields?.brand],
  ];
  return (
    <aside className="case-column" aria-label="Your search details">
      <section className="case-summary">
        <div className="section-label">
          <span>Your search</span>
          <Icon name="bag" />
        </div>
        <h2>
          A few details
          <br />
          make the difference.
        </h2>
        <p>
          We'll build your description as we talk. You can correct anything
          along the way.
        </p>
        <dl>
          {values.map(([label, value]) => (
            <div className="detail-row" key={label}>
              <dt>{label}</dt>
              <dd>
                {value || <span className="not-yet">Not provided</span>}
                {value &&
                  fields?.uncertain?.includes(
                    label === "Colour"
                      ? "colour"
                      : label === "Brand"
                        ? "brand"
                        : "",
                  ) && <span> · uncertain</span>}
              </dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="desk-note" id="desk-info">
        <Icon name="help" />
        <h3>A possible match is a first step.</h3>
        <p>
          Our desk team checks identifying details before handing anything over.
          We won't read out the contents of found items.
        </p>
      </section>
      <p className="fictional-note">
        Demonstration only. Riverside Mall and all inventory records are
        fictional.
      </p>
    </aside>
  );
}
