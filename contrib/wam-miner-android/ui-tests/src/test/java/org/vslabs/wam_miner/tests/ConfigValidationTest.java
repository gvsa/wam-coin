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
import org.testng.annotations.AfterClass;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.Test;
import org.vslabs.wam_miner.utils.LayoutIdParser;

import io.appium.java_client.android.AndroidDriver;
import io.appium.java_client.android.options.UiAutomator2Options;

public class ConfigValidationTest {

    private AndroidDriver driver;
    private WebDriverWait wait;
    private Map<String, By> mainLocators;
    private Map<String, By> configLocators;

    // Valid WAM address matching ^(wam1([a-z0-9]{39}|[a-z0-9]{59})|[Ww][1-9A-HJ-NP-Za-km-z]{33})$
    private static final String VALID_WAM_ADDRESS = "wam1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq";

    @BeforeClass
    public void setUpAndNavigateToConfig() throws MalformedURLException {
        mainLocators = LayoutIdParser.parseLayoutIds("activity_main.xml");
        configLocators = LayoutIdParser.parseLayoutIds("activity_config.xml");

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

        driver = new AndroidDriver(URI.create("http://127.0.0.1:4723").toURL(), options);
        wait = new WebDriverWait(driver, Duration.ofSeconds(20));

        // Navigate from MainActivity to ConfigActivity once for all field validation checks
        wait.until(ExpectedConditions.elementToBeClickable(mainLocators.get("getStartedBtn"))).click();
        wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("form")));
    }

    @Test(priority = 1, description = "Verify blank wallet address triggers error_address")
    public void testBlankWalletAddressValidation() {
        clearAllFields();
        driver.findElement(configLocators.get("saveConfigBtn")).click();

        WebElement errorAddress = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("error_address")));
        Assert.assertEquals(errorAddress.getText().trim(), "Wallet address cannot be blank!");
    }

    @Test(priority = 2, description = "Verify invalid WAM wallet format triggers error_address and clears on edit")
    public void testInvalidWalletFormatValidation() {
        WebElement addressInput = driver.findElement(configLocators.get("input_address"));
        addressInput.clear();
        addressInput.sendKeys("invalid_wallet_12345");

        driver.findElement(configLocators.get("saveConfigBtn")).click();

        WebElement errorAddress = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("error_address")));
        Assert.assertEquals(errorAddress.getText().trim(), "Please provide a valid WAM wallet address.");

        // Verify setupErrorClearer hides the error when text changes
        addressInput.clear();
        addressInput.sendKeys(VALID_WAM_ADDRESS);
        Assert.assertTrue(wait.until(ExpectedConditions.invisibilityOfElementLocated(configLocators.get("error_address"))),
                "error_address should hide once wallet text is modified");
    }

    @Test(priority = 3, description = "Verify blank Stratum URL triggers error_stratum")
    public void testBlankStratumUrlValidation() {
        WebElement addressInput = driver.findElement(configLocators.get("input_address"));
        addressInput.clear();
        addressInput.sendKeys(VALID_WAM_ADDRESS);

        driver.findElement(configLocators.get("input_stratum")).clear();
        driver.findElement(configLocators.get("saveConfigBtn")).click();

        WebElement errorStratum = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("error_stratum")));
        Assert.assertEquals(errorStratum.getText().trim(), "Stratum URL cannot be blank");
    }

    @Test(priority = 4, description = "Verify blank Port triggers error_port")
    public void testBlankPortValidation() {
        WebElement stratumInput = driver.findElement(configLocators.get("input_stratum"));
        stratumInput.clear();
        stratumInput.sendKeys("stratum.wam-pool.org");

        driver.findElement(configLocators.get("input_port")).clear();
        driver.findElement(configLocators.get("saveConfigBtn")).click();

        WebElement errorPort = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("error_port")));
        Assert.assertEquals(errorPort.getText().trim(), "port cannot be blank!");
    }

    @Test(priority = 5, description = "Verify invalid characters in Worker Name trigger error_worker")
    public void testInvalidWorkerNameValidation() {
        WebElement portInput = driver.findElement(configLocators.get("input_port"));
        portInput.clear();
        portInput.sendKeys("3333");

        // Spaces and '@' violate [a-zA-Z0-9_-]+
        WebElement workerInput = driver.findElement(configLocators.get("input_worker"));
        workerInput.clear();
        workerInput.sendKeys("bad worker@name!");

        driver.findElement(configLocators.get("saveConfigBtn")).click();

        WebElement errorWorker = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("error_worker")));
        Assert.assertTrue(errorWorker.getText().contains("Only letters, numbers and hyphen"),
                "Expected worker validation message, got: " + errorWorker.getText());
    }

    private void clearAllFields() {
        driver.findElement(configLocators.get("input_address")).clear();
        driver.findElement(configLocators.get("input_stratum")).clear();
        driver.findElement(configLocators.get("input_port")).clear();
        driver.findElement(configLocators.get("input_worker")).clear();
    }

    @AfterClass(alwaysRun = true)
    public void tearDown() {
        if (driver != null) {
            driver.quit();
        }
    }
}
