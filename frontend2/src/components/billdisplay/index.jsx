// Will have to handle fetching the bill text, and formatting it correctly.

import React, { useEffect, useState } from "react";
import lodash from "lodash";

import SyncLoader from "react-spinners/SyncLoader";
import { Tooltip } from "@blueprintjs/core";

import { getBillVersionText } from "common/api.js";

// TODO: move this somewhere in scss?
const styles = {
  "quoted-block": {
    borderWidth: "1px",
    borderStyle: "solid",
    borderColor: "gray",
    backgroundColor: "lightgray",
  },
  unchanged: {},

  added: {
    backgroundColor: "#cdffd8",
  },
  removed: {
    backgroundColor: "#ffdce0",
    textDecoration: "line-through",
    textDecorationColor: "#FF576B",
  },
  centered: {
    textAlign: "center",
  },
  col_a: {
    height: "90vh",
    overflowX: "wrap",
  },
  col: {
    height: "90vh",
    overflowX: "wrap",
  },
  sidebar: {},
};
function Minimap(props) {
  const target = document.getElementById("bill-view");
  const scrollTarget = document.getElementById("bill-viewer-content");
  const minimap = document.getElementById("minimap");
  const [cloned, setCloned] = useState(null);
  const [ref, setRef] = useState(null);
  const [styleOverride, setStyleOverride] = useState({});
  const [highlightStyle, setHighlightStyle] = useState({});
  useEffect(() => {
    if (target !== null && cloned === null) {
      const clone = target.cloneNode(true);
      clone.id = "bill-view-clone";
      setCloned(clone);
    }
  });
  if (scrollTarget !== null) {
    scrollTarget.onscroll = () => {
      const mmh = document.getElementById("minimap-highlight");
      mmh.style.top = `${scrollTarget.scrollTop * 0.9}px`;
      mmh.style.height = `${scrollTarget.clientHeight * 0.9}px`;
      //mmh.style.height = "calc(10vh - 30px)";
    };
  }
  useEffect(() => {
    if (cloned && ref.children.length == 1) {
      ref.insertBefore(cloned, ref.children[0]);
      setStyleOverride({
        top: `${target.offsetTop}px`,
      });
    }
  }, [cloned]);
  function handleClick(event) {
    console.log(event);
    console.log(event.clientX);
    console.log(event.clientY);
    const calcPosition = (event.clientY - target.offsetTop) * 10;
    scrollTarget.scrollTo(0, calcPosition);
    return false;
  }
  return (
    <div
      className="minimap"
      id="minimap"
      ref={setRef}
      style={styleOverride}
      onClick={handleClick}
    >
      <div id="minimap-highlight" style={highlightStyle}></div>
    </div>
  );
}
function BillDisplay(props) {
  // TODO: Add minimap scrollbar
  // *TODO*: Start using the action list to render a list of parsed actions
  // TODO: Add permalink feature
  // TODO: Add highlight feature to permalink in the url ?link=a/1/ii&highlight=a/1/ii,a/1/v
  const [textTree, setTextTree] = useState({});
  useEffect(() => {
    const { congress, chamber, billNumber, billVersion } = props;
    setTextTree({ loading: true });
    getBillVersionText(congress, chamber, billNumber, billVersion).then(setTextTree);
  }, [props.billVersion]);
  function renderRecursive(node) {
    return (
      <>
        {lodash.map(
          node.children || [],
          (
            {
              legislation_content_id,
              content_str,
              content_type,
              section_display,
              heading,
              action,
              children = [],
            },
            ind
          ) => {
            let actionStr = lodash
              .chain(action)
              .map(lodash.keys)
              .flatten()
              .remove(x => x !== "changed" && x !== "parsed_cite")
              .value()
              .join(", ");
            if (heading !== undefined) {
              return (
                <div
                  name={legislation_content_id}
                  key={ind}
                  className={`bill-content-${content_type} bill-content-section`}
                  style={
                    content_type === "legis-body"
                      ? {}
                      : styles[content_type] || styles.section
                  }
                  className="bill-content"
                >
                  <Tooltip
                    content={actionStr}
                    disabled={actionStr === "" || props.showTooltips !== true}
                  >
                    <span>
                      <b>
                        {section_display} {heading}
                      </b>
                      <p className="bill-content-continue">{content_str}</p>
                    </span>
                  </Tooltip>
                  {renderRecursive({ children })}
                </div>
              );
            } else {
              return (
                <div
                  name={legislation_content_id}
                  key={ind}
                  className={`bill-content-${content_type}  bill-content-section`}
                  style={
                    content_type === "legis-body"
                      ? {}
                      : styles[content_type] || styles.section
                  }
                >
                  {section_display || content_str ? (
                    <Tooltip
                      content={actionStr}
                      disabled={actionStr === "" || props.showTooltips !== true}
                    >
                      <span>
                        <span style={{ fontWeight: "bolder" }}>{section_display}</span>{" "}
                        <span>{content_str}</span>
                      </span>
                    </Tooltip>
                  ) : null}
                  {renderRecursive({ children })}
                </div>
              );
            }
          }
        )}
      </>
    );
  }
  if (textTree.loading) {
    return <SyncLoader loading={true} />;
  }
  return (
    <>
      <div id="bill-view" className="content-holder">
        {renderRecursive(textTree)}
      </div>{" "}
      <Minimap />
    </>
  );
}

export default BillDisplay;
