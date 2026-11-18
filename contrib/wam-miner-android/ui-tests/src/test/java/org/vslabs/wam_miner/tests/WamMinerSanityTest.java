package org.vslabs.wam_miner.tests;

import java.net.MalformedURLException;
import java.net.URI;
import java.time.Duration;
import java.util.Map;

import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;
import org.vslabs.wam_miner.utils.LayoutIdParser;

import io.appium.java_client.android.AndroidDriver;
import io.appium.java_client.android.options.UiAutomator2Options;

public class WamMinerSanityTest {

    private AndroidDriver driver;
    private WebDriverWait wait;
    private Map<String, By> mainLocators;
    private Map<String, By> dialogLocators;
	private Map<String, By> configLocators;

    @BeforeClass
    public void loadLayouts() {
        mainLocators = LayoutIdParser.parseLayoutIds("activity_main.xml");
        dialogLocators = LayoutIdParser.parseLayoutIds("dialog_about.xml");
        configLocators = LayoutIdParser.parseLayoutIds("activity_config.xml");
    }

    @BeforeMethod
    public void setUp() throws MalformedURLException {
        String apkPath = System.getProperty("apk.path");

        UiAutomator2Options options = new UiAutomator2Options()
                .setPlatformName("Android")
                .setAutomationName("UiAutomator2")
                .setAppPackage("org.vslabs.wam_miner")
                .setAppActivity("org.vslabs.wam_miner.SplashActivity")
                .setAppWaitActivity("org.vslabs.wam_miner.*")
                .setAutoGrantPermissions(true);

        if (apkPath != null && !apkPath.isEmpty()) {
            options.setApp(apkPath);
        }

        driver = new AndroidDriver(URI.create("http://127.0.0.1:4723/").toURL(), options);
        wait = new WebDriverWait(driver, Duration.ofSeconds(20));
    }

    @Test(priority = 1, description = "Verify app launches past splash, renders MainActivity, and opens About dialog")
    public void testAppSanity() {
        // 1. Wait for MainActivity container
        WebElement mainView = wait.until(ExpectedConditions.visibilityOfElementLocated(mainLocators.get("main")));
        Assert.assertTrue(mainView.isDisplayed(), "Main screen did not load after SplashActivity");

        // 2. Verify MainActivity parsed elements
        Assert.assertTrue(driver.findElement(mainLocators.get("app_title")).isDisplayed(), "App title missing");
        Assert.assertTrue(driver.findElement(mainLocators.get("hwinfo")).isDisplayed(), "Hardware info missing");
        Assert.assertTrue(driver.findElement(mainLocators.get("getStartedBtn")).isEnabled(), "Get Started button disabled");

        // 3. Open About dialog and verify parsed elements
        driver.findElement(mainLocators.get("aboutBtn")).click();

        WebElement versionTxt = wait.until(ExpectedConditions.visibilityOfElementLocated(dialogLocators.get("txt_dialog_version")));
        Assert.assertTrue(versionTxt.isDisplayed(), "Dialog version text missing");
        Assert.assertTrue(driver.findElement(dialogLocators.get("txt_dialog_build")).isDisplayed(), "Dialog build text missing");
        Assert.assertTrue(driver.findElement(dialogLocators.get("btn_dialog_core")).isDisplayed(), "Wam Core button missing");
        Assert.assertTrue(driver.findElement(dialogLocators.get("btn_dialog_dev")).isDisplayed(), "Android dev button missing");
    }

    @Test(priority = 2, description = "Verify ConfigActivity form loads and action buttons are enabled")
    public void TestConfigActivity() {
        // 1. Wait for MainActivity and navigate to ConfigActivity
        WebElement getStartedBtn = wait.until(ExpectedConditions.elementToBeClickable(mainLocators.get("getStartedBtn")));
        getStartedBtn.click();

        // 2. Verify ConfigActivity top bar and main TableLayout form are loaded
        WebElement topBar = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("topBarTitle")));
        Assert.assertTrue(topBar.isDisplayed(), "ConfigActivity top bar title missing");
        Assert.assertTrue(driver.findElement(configLocators.get("form")).isDisplayed(), "Config form TableLayout did not load");

        // 3. Verify form input fields are visible
        Assert.assertTrue(driver.findElement(configLocators.get("input_address")).isDisplayed(), "Wallet address field missing");
        Assert.assertTrue(driver.findElement(configLocators.get("input_stratum")).isDisplayed(), "Stratum URL field missing");
        Assert.assertTrue(driver.findElement(configLocators.get("input_port")).isDisplayed(), "Port field missing");
        Assert.assertTrue(driver.findElement(configLocators.get("input_worker")).isDisplayed(), "Worker name field missing");
        Assert.assertTrue(driver.findElement(configLocators.get("input_cores")).isDisplayed(), "Cores counter missing");

        // 4. Verify all buttons on ConfigActivity are displayed and enabled
        WebElement coreMinusBtn = driver.findElement(configLocators.get("coreminus"));
        WebElement corePlusBtn = driver.findElement(configLocators.get("coreplus"));
        WebElement saveConfigBtn = driver.findElement(configLocators.get("saveConfigBtn"));
        WebElement startMiningBtn = driver.findElement(configLocators.get("startnativemining"));

        Assert.assertTrue(coreMinusBtn.isDisplayed() && coreMinusBtn.isEnabled(), "Core minus (-) button is not enabled");
        Assert.assertTrue(corePlusBtn.isDisplayed() && corePlusBtn.isEnabled(), "Core plus (+) button is not enabled");
        Assert.assertTrue(saveConfigBtn.isDisplayed() && saveConfigBtn.isEnabled(), "Save Config button is not enabled");
        Assert.assertTrue(startMiningBtn.isDisplayed() && startMiningBtn.isEnabled(), "Start Native Mining button is not enabled");
    }
    
    @AfterMethod(alwaysRun = true)
    public void tearDown() {
        if (driver != null) {
            driver.quit();
        }
    }
}
