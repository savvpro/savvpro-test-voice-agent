import type { Business } from "@/lib/types";

export function StudioServices({
  business,
  hidden,
  disabled,
  onStart,
  onBook,
}: {
  business: Business | null;
  hidden: boolean;
  disabled: boolean;
  onStart: () => void;
  onBook: (service: Business["services"][number]) => void;
}) {
  const haircut = business?.services.find(
    (service) => service.id === "haircut",
  );
  const beard = business?.services.find((service) => service.id === "beard");
  const currency = business?.currency || "PKR";
  const price = (value: number) =>
    `${currency} ${value.toLocaleString("en-PK")}`;

  return (
    <section
      className="services-view"
      aria-label="Studio services workspace"
      hidden={hidden}
    >
      <section className="panel services-catalog" aria-label="Service catalog">
        <h2 className="mini-label">SERVICES</h2>
        {business ? (
          <ul className="services-rows">
            {business.services.map((service) => {
              const saving =
                service.id === "combo" && haircut && beard
                  ? haircut.price + beard.price - service.price
                  : 0;
              return (
                <li key={service.id}>
                  <div className="service-description">
                    <div>
                      <h3>{service.name}</h3>
                      {saving > 0 && (
                        <span className="service-saving">
                          Save {price(saving)}
                        </span>
                      )}
                    </div>
                    <p>{service.minutes} min</p>
                  </div>
                  <strong className="service-price">
                    {price(service.price)}
                  </strong>
                  <button
                    className="button secondary"
                    aria-label={`Book ${service.name}`}
                    disabled={disabled}
                    onClick={() => onBook(service)}
                  >
                    Book
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="services-unavailable">
            Studio details are unavailable. Return to the conversation to check
            the connection.
          </p>
        )}
      </section>
      <div className="services-aside">
        <section
          className="services-invitation"
          aria-labelledby="services-invitation-title"
        >
          <h2 id="services-invitation-title">Prefer to talk?</h2>
          <p>Ask the receptionist to check availability and book for you.</p>
          <button className="button" onClick={onStart}>
            Start a conversation
          </button>
        </section>
        <section className="panel services-hours" aria-label="Opening hours">
          <h2 className="mini-label">OPENING HOURS</h2>
          <dl>
            <div>
              <dt>{business?.hours.split(",")[0] || "Opening days"}</dt>
              <dd>
                {business?.hours.split(",").slice(1).join(",").trim() || "—"}
              </dd>
            </div>
            <div>
              <dt>Sunday</dt>
              <dd>Closed</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>{business?.timezone || "—"}</dd>
            </div>
          </dl>
        </section>
      </div>
    </section>
  );
}
