import { helper } from "./utils";
import { widget } from "@lib/widget";
import express from "express";

export function run() {
  helper();
  widget();
  return express;
}
