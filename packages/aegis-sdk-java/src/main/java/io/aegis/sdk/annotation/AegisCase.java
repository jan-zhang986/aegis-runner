package io.aegis.sdk.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 用例元数据注解：声明用例编号、需求溯源与业务风险
 */
@Target({ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface AegisCase {
    /** 用例唯一标识，如 TC-SMS-001 */
    String id();

    /** 关联需求编号，如 REQ-224 */
    String req() default "";

    /** 用例标题，若为空则默认使用方法名 */
    String title() default "";

    /** 核心业务风险描述（如：高频短信轰炸导致通道封禁与财务资损） */
    String risk() default "";

    /** 优先级：P0, P1, P2 */
    String priority() default "P1";

    /** 标签列表，如 {"smoke", "security"} */
    String[] tags() default {};

    /** 详细描述 */
    String description() default "";
}
