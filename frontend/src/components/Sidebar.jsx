import { NavLink } from "react-router-dom";

const links = [
  ["/", "Home / Summary"],
  ["/topics", "Scraped Topics"],
  ["/engine-studio", "Engine Studio"],
  ["/library", "Content Library"],
  ["/settings", "Settings"],
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <h1>NOVA</h1>
      {links.map(([to, label]) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          end={to === "/"}
        >
          {label}
        </NavLink>
      ))}
    </aside>
  );
}
