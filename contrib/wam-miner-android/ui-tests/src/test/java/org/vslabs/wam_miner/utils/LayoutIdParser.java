package org.vslabs.wam_miner.utils;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

import org.openqa.selenium.By;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import io.appium.java_client.AppiumBy;

public class LayoutIdParser {

    private static final String ANDROID_NS = "http://schemas.android.com/apk/res/android";
    private static final String PKG = "org.vslabs.wam_miner";

    public static Map<String, By> parseLayoutIds(String layoutFileName) {
        Map<String, By> locators = new HashMap<String, By>();
        try {
            File xmlFile = new File("../app/src/main/res/layout/" + layoutFileName);
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document doc = builder.parse(xmlFile);

            NodeList nodes = doc.getElementsByTagName("*");
            for (int i = 0; i < nodes.getLength(); i++) {
                Element element = (Element) nodes.item(i);
                String rawId = element.getAttributeNS(ANDROID_NS, "id");
                if (rawId != null && rawId.contains("/")) {
                    String cleanId = rawId.substring(rawId.indexOf("/") + 1);
                    locators.put(cleanId, AppiumBy.id(PKG + ":id/" + cleanId));
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse layout file: " + layoutFileName, e);
        }
        return locators;
    }
}
