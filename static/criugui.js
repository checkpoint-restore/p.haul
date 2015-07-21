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

/* Show two trees.
 * TODO: don't hardcode this. */
var targetData = [
    { name: "localhost", address: "http://127.0.0.1:8080" },
    { name: "other machine", address: "http://some-other-machine-also-running-criugui.py:8080" },
];

var pstrees = d3.select("#pstree-container").selectAll("div").data(targetData);
var enter = pstrees.enter().append("div")
    .classed("col-md-6", true)
    .append("div")
    .classed({"panel" : true, "panel-default" : true, "pstree" : true});

enter.append("div")
    .classed("panel-heading", true)
    .text(function(d) { return d.name; });

enter.append("svg")
    .classed("panel-body", true)
    .attr({ width : "100%", height : "450" })
    .each(function(d) {
      new PSTree(d3.select(this)).listen(d.address);
    });
