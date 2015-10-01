/*!
 * Copyright (C) 2015 Red Hat Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

function stringifyProc(proc) {
  return proc.name + " (" + proc.id + ")";
}

/* Migrate a proccess from the given source to the given target.  This function
 * calls the web API to interact with CRIU, and updates the page appropriately
 * when the result of the migration is available. */
function migrate(proc, source, target) {
  if (source == target) {
    console.log("source and target are the same machine.");
    return;
  }

  /* Add an alert to let the user know that the migration has started. */
  var alert = insertAlert();
  alert.classed("alert-info", true);

  var p = alert.append("p");
  p.append("b").text("Info: ");
  p.append("span").text("Migrating ");
  p.append("code").text(stringifyProc(proc));
  p.append("span");
  p.append("span").text(" from ");
  p.append("code").text(source.name);
  p.append("span").text(" to ");
  p.append("code").text(target.name);

  _migrate(proc, source, target);
}

function _migrate(proc, source, target) {
  var req = new XMLHttpRequest();

  req.onload = function() {
    console.log(this.responseText);
    var resp = JSON.parse(this.responseText);

    /* Add an alert to the page with info on the result of the dump. */
    var alert = insertAlert();
    var p = alert.append("p");

    if (!resp.succeeded) {
      alert.classed("alert-danger", true);

      p.append("b").text("Migration Failed: ");
      p.append("span").text("There was a problem migrating ");
      p.append("code").text(stringifyProc(proc));
      p.append("span").text(" from " );
      p.append("code").text(source.name);

      alert.append("br");
      alert.append("pre").text(resp.why);
    }
  };

  req.open("get", source.address + "/migrate?pid=" + proc.id, true);
  req.send();
}

/* Add an alert div to the page with some preset styles and a close button. */
function insertAlert() {
  var alert = d3.select("#alerts").insert("div", ":first-child")
      .attr("role", "alert")
      .classed({ "alert" : true, "alert-dismissible" : true });

  alert.append("a")
      .attr("data-dismiss", "alert")
      .classed("close", true)
      .text("×");

  return alert;
}
